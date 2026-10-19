"""
synthesis.py
Funzioni di sintesi vocale: Piper TTS (offline), Edge TTS (online), download modelli.

Questo modulo è importato sia dal web server (tts_engine.py) sia dalla CLI (leggi.py).
Non deve mai chiamare sys.exit() — gli errori sono segnalati tramite eccezioni.
"""

import io
import os
import tempfile
import urllib.request
import wave
from pathlib import Path

from src.config import (
    VOICE_DIR,
    VOICE_URLS,
    error,
    info,
    warn,
)

# Seconds without data before a stalled model download fails (per socket
# operation, not for the whole ~60 MB transfer).
DOWNLOAD_TIMEOUT_S = 30
_CHUNK_BYTES = 1024 * 64


def _scarica_file(url: str, dest) -> None:
    """Scarica ``url`` su ``dest`` passando da un file ``.part``.

    Il file finale compare solo a download completo: un'interruzione non
    lascia un modello troncato che ``dest.exists()`` darebbe per buono. Il
    ``.part`` ha un nome unico, perché web e CLI possono scaricare insieme.
    """
    fd, nome_parziale = tempfile.mkstemp(dir=dest.parent, prefix=f"{dest.name}.", suffix=".part")
    parziale = Path(nome_parziale)
    try:
        with (
            os.fdopen(fd, "wb") as f,
            urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_S) as response,  # noqa: S310
        ):
            total = int(response.headers.get("Content-Length", 0))
            scaricati = 0
            while chunk := response.read(_CHUNK_BYTES):
                f.write(chunk)
                scaricati += len(chunk)
                if total:
                    print(f"\r  {scaricati / total * 100:.1f}%", end="", flush=True)
        if scaricati == 0:
            raise OSError("download vuoto: il server non ha inviato dati")
        if total and scaricati != total:
            raise OSError(f"download incompleto: {scaricati} di {total} byte")
        parziale.replace(dest)
    finally:
        parziale.unlink(missing_ok=True)


def scarica_voce_piper():
    """Scarica il modello vocale Piper se non già presente.

    Raises
    ------
    RuntimeError
        Se il download fallisce.
    """
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    for dest, url in VOICE_URLS.items():
        if dest.exists():
            info(f"Voce già presente: {dest.name}")
            continue
        warn(f"Scarico {dest.name} ...")
        try:
            _scarica_file(url, dest)
            print()
            info(f"{dest.name} scaricato.")
        except Exception as e:
            error(f"Errore durante il download: {e}")
            raise RuntimeError(f"Download voce Piper fallito: {e}") from e


def sintetizza_piper(voce_piper, testo: str, sample_rate: int) -> bytes:
    """Sintetizza testo con Piper TTS.

    Parameters
    ----------
    voce_piper : PiperVoice
        Istanza del modello Piper caricato.
    testo : str
        Testo da sintetizzare.
    sample_rate : int
        Frequenza di campionamento del modello.

    Returns
    -------
    bytes
        Audio WAV in memoria.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        voce_piper.synthesize_wav(testo, wf)
    return buf.getvalue()


class EdgeNoAudioError(RuntimeError):
    """Edge TTS answered without any audio chunk."""


async def sintetizza_edge(
    voice_id: str,
    testo: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> bytes:
    """Sintetizza testo con Edge TTS (Microsoft, richiede internet).

    Parameters
    ----------
    voice_id : str
        Identificativo voce Edge TTS (es. "it-IT-GiuseppeMultilingualNeural").
    testo : str
        Testo da sintetizzare.
    rate : str, optional
        Velocità di lettura (es. "+13%", "-8%"). Default: "+0%".
    pitch : str, optional
        Tono della voce (es. "+5Hz", "-3Hz"). Default: "+0Hz".

    Returns
    -------
    bytes
        Audio MP3 in memoria.

    Raises
    ------
    EdgeNoAudioError
        Se Edge chiude lo stream senza inviare audio: un MP3 vuoto finirebbe
        in cache come se fosse valido e il player resterebbe muto.
    """
    import edge_tts

    comm = edge_tts.Communicate(testo, voice_id, rate=rate, pitch=pitch)
    buf = io.BytesIO()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    if not buf.getvalue():
        raise EdgeNoAudioError(f"Edge TTS returned no audio for voice {voice_id}")
    return buf.getvalue()
