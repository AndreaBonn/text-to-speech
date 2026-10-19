"""
chapters.py
Capitoli ID3 (CHAP/CTOC) nell'MP3 salvato: uno per titolo del documento sorgente.

Gli istanti vengono dalla timeline reale del file unito (pacchetti letti da
ffprobe), non da una somma di durate: un segmento con header Xing/LAME dichiara
una durata senza ritardo e padding dell'encoder, ma nel flusso unito quei frame
restano. I capitoli si scrivono con ffmpeg da un file FFMETADATA, con
``-c copy``: l'audio non viene ricodificato.
"""

import bisect
import io
import logging
import re
import subprocess
import tempfile
import wave
from pathlib import Path

from src.titles import Titolo

log = logging.getLogger(__name__)

# Same budget as the CLI encoder (leggi._timeout_ffmpeg): ffprobe and a copy
# remux are far faster than encoding, so the margin only grows.
_MIN_TIMEOUT_S = 30
_BYTES_PER_TIMEOUT_S = 1024 * 1024
_FFMETADATA_SPECIAL = re.compile(r"([=;#\\\n])")


class ProbeError(ValueError):
    """ffprobe non ha restituito pacchetti leggibili per l'MP3."""


# ffmpeg/ffprobe missing (OSError), failing or timing out (SubprocessError), a probe
# with no packets (ProbeError), or a Piper WAV that does not parse (wave.Error,
# EOFError). Chapters are optional: any of these saves the MP3 without them rather
# than losing the whole file. Programming errors are not listed, so they still crash.
_ERRORI_CAPITOLI = (OSError, subprocess.SubprocessError, ProbeError, wave.Error, EOFError)


def _timeout_s(n_bytes: int) -> float:
    return max(_MIN_TIMEOUT_S, n_bytes / _BYTES_PER_TIMEOUT_S)


def _normalizza(testo: str) -> str:
    return " ".join(testo.split()).casefold()


def trova_capitoli(paragrafi: list[str], titoli: list[Titolo]) -> list[tuple[int, str]]:
    """Aggancia i titoli ai paragrafi, in ordine: ``[(indice paragrafo, titolo), ...]``.

    Ogni titolo si cerca dopo il paragrafo del precedente, così un titolo che
    ricorre nel testo prende l'occorrenza giusta. Un titolo senza paragrafo
    viene saltato. Il primo capitolo parte dal paragrafo 0 anche se prima del
    primo titolo c'è del testo: nessun tratto di audio resta fuori dai capitoli.
    """
    normalizzati = [_normalizza(p) for p in paragrafi]
    capitoli: list[tuple[int, str]] = []
    cursore = 0
    for titolo in titoli:
        chiave = _normalizza(titolo.paragrafo)
        try:
            indice = normalizzati.index(chiave, cursore)
        except ValueError:
            log.warning("Titolo senza paragrafo corrispondente, capitolo saltato: %r", titolo.testo)
            continue
        capitoli.append((indice, titolo.testo))
        cursore = indice + 1
    if capitoli:
        capitoli[0] = (0, capitoli[0][1])
    return capitoli


def inizi_capitoli(
    inizi_paragrafi: list[float], capitoli: list[tuple[int, str]]
) -> list[tuple[float, str]]:
    """Istante d'inizio di ogni capitolo; il primo sempre a 0."""
    risultato = [(inizi_paragrafi[indice], titolo) for indice, titolo in capitoli]
    if risultato:
        risultato[0] = (0.0, risultato[0][1])
    return risultato


def metadata_ffmetadata(capitoli: list[tuple[float, str]], fine_s: float) -> str:
    """File FFMETADATA1 con un ``[CHAPTER]`` per capitolo, in millisecondi.

    Ogni capitolo finisce dove inizia il successivo, l'ultimo a ``fine_s``.
    """
    righe = [";FFMETADATA1"]
    confini = [round(inizio * 1000) for inizio, _ in capitoli] + [round(fine_s * 1000)]
    for i, (_, titolo) in enumerate(capitoli):
        escapato = _FFMETADATA_SPECIAL.sub(r"\\\1", titolo)
        righe += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={confini[i]}",
            f"END={confini[i + 1]}",
            f"title={escapato}",
        ]
    return "\n".join(righe) + "\n"


def timeline_mp3(mp3: bytes, offsets: list[int]) -> tuple[list[float], float]:
    """Istanti dei byte ``offsets`` nel flusso MP3 e durata totale, letti da ffprobe.

    L'istante di un offset è il ``pts`` del primo pacchetto che inizia da lì
    in poi: la stessa timeline che vede il lettore, giunzioni comprese.
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-f",
            "mp3",
            "-i",
            "pipe:0",
            "-show_entries",
            "packet=pts_time,duration_time,pos",
            "-of",
            "csv=p=0",
        ],
        input=mp3,
        capture_output=True,
        check=True,
        timeout=_timeout_s(len(mp3)),
    )
    pts, posizioni, durata, riga = [], [], 0.0, ""
    try:
        for riga in result.stdout.decode().splitlines():
            # A packet with side data (the encoder's skip samples) gets an extra column.
            inizio, durata_txt, pos = riga.split(",")[:3]
            pts.append(float(inizio))
            posizioni.append(int(pos))
            durata = float(durata_txt)
    except ValueError as err:
        raise ProbeError(f"unreadable ffprobe packet line: {riga!r}") from err
    if not pts:
        raise ProbeError("ffprobe returned no packets")
    fine = pts[-1] + durata
    inizi = [
        pts[i] if (i := bisect.bisect_left(posizioni, offset)) < len(pts) else fine
        for offset in offsets
    ]
    return inizi, fine


def scrivi_capitoli(mp3: bytes, capitoli: list[tuple[float, str]], fine_s: float) -> bytes:
    """Restituisce ``mp3`` con i capitoli ID3 (CHAP/CTOC), senza ricodificare l'audio."""
    with tempfile.TemporaryDirectory() as tmp:
        meta = Path(tmp) / "chapters.txt"
        meta.write_text(metadata_ffmetadata(capitoli, fine_s), encoding="utf-8")
        result = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "mp3",
                "-i",
                "pipe:0",
                "-i",
                str(meta),
                "-map",
                "0:a",
                "-map_metadata",
                "1",
                "-map_chapters",
                "1",
                "-c",
                "copy",
                "-id3v2_version",
                "3",
                "-f",
                "mp3",
                "pipe:1",
            ],
            input=mp3,
            capture_output=True,
            check=True,
            timeout=_timeout_s(len(mp3)),
        )
    log.info("Capitoli ID3 scritti: %d", len(capitoli))
    return result.stdout


def unisci_con_capitoli(segmenti: list[bytes], capitoli: list[tuple[int, str]]) -> bytes:
    """Unisce gli MP3 dei paragrafi e, se ci sono capitoli, li scrive nel file.

    Senza capitoli restituisce la semplice concatenazione dei byte, come prima;
    la stessa concatenazione, con un warning, se ffmpeg o ffprobe falliscono.
    I capitoli che iniziano dopo l'ultimo segmento (salvataggio interrotto)
    vengono ignorati.
    """
    unito = b"".join(segmenti)
    capitoli = [c for c in capitoli if c[0] < len(segmenti)]
    if not capitoli:
        return unito
    offsets, cursore = [], 0
    for segmento in segmenti:
        offsets.append(cursore)
        cursore += len(segmento)
    try:
        inizi, fine = timeline_mp3(mp3=unito, offsets=offsets)
        return scrivi_capitoli(mp3=unito, capitoli=inizi_capitoli(inizi, capitoli), fine_s=fine)
    except _ERRORI_CAPITOLI:
        log.warning("Capitoli ID3 non scritti, MP3 salvato senza capitoli.", exc_info=True)
        return unito


def _durata_wav(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        if wf.getframerate() == 0:
            raise wave.Error("WAV with framerate 0")
        return wf.getnframes() / wf.getframerate()


def aggiungi_capitoli_wav(path: Path, lista_wav: list[bytes], capitoli: list[tuple[int, str]]):
    """Scrive i capitoli in un MP3 nato da un'unica codifica dei WAV ``lista_wav`` uniti.

    È il caso di Piper: gli inizi dei paragrafi si ricavano esatti dal numero
    di campioni di ogni WAV. Il file viene sostituito solo a scrittura riuscita;
    se ffmpeg o ffprobe falliscono resta l'MP3 senza capitoli, con un warning.
    """
    capitoli = [c for c in capitoli if c[0] < len(lista_wav)]
    if not capitoli:
        return
    temporaneo = path.with_suffix(".chapters.tmp")
    try:
        inizi, istante = [], 0.0
        for wav_bytes in lista_wav:
            inizi.append(istante)
            istante += _durata_wav(wav_bytes)
        mp3 = path.read_bytes()
        _, fine = timeline_mp3(mp3=mp3, offsets=[])
        con_capitoli = scrivi_capitoli(
            mp3=mp3, capitoli=inizi_capitoli(inizi, capitoli), fine_s=fine
        )
        temporaneo.write_bytes(con_capitoli)
        temporaneo.replace(path)
    except _ERRORI_CAPITOLI:
        temporaneo.unlink(missing_ok=True)
        log.warning("Capitoli ID3 non scritti, MP3 salvato senza capitoli.", exc_info=True)
