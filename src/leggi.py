#!/usr/bin/env python3
"""
leggi.py
Legge ad alta voce file di testo in italiano usando Piper TTS o Edge TTS.
Supporta: Markdown, TXT, EPUB, DOCX, HTML, PDF.

Uso:
    python leggi.py file.md
    python leggi.py documento.pdf --voice giuseppe
    python leggi.py libro.epub --voice paola --salva output.mp3

Voci disponibili:
    giuseppe  - Edge TTS, maschile, multilingue (default, richiede internet)
    isabella  - Edge TTS, femminile
    elsa      - Edge TTS, femminile
    diego     - Edge TTS, maschile
    paola     - Piper TTS, femminile, offline

Setup iniziale (una sola volta):
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
"""

import argparse
import asyncio
import io
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from src.config import (
    ALL_VOICES,
    DATA_OUTPUT,
    DEFAULT_VOICE,
    EDGE_VOICES,
    GREEN,
    NC,
    PIPER_VOICES,
    PLATFORM,
    VOICE_JSON,
    VOICE_MODEL,
    error,
    info,
    suggerisci_installazione,
    verifica_prerequisiti,
)
from src.synthesis import scarica_voce_piper, sintetizza_edge, sintetizza_piper

# ─── Utilità audio ───────────────────────────────────────────────────────────


def wav_a_mp3(wav_bytes: bytes, output_path: Path):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            "pipe:0",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "128k",
            "-loglevel",
            "error",
            str(output_path),
        ],
        input=wav_bytes,
        check=True,
        timeout=30,
    )


def concatena_wav(lista_wav: list[bytes], sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf_out:
        wf_out.setnchannels(1)
        wf_out.setsampwidth(2)
        wf_out.setframerate(sample_rate)
        for wav_bytes in lista_wav:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf_in:
                wf_out.writeframes(wf_in.readframes(wf_in.getnframes()))
    return buf.getvalue()


def concatena_mp3(lista_mp3: list[bytes], output_path: Path):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            "concat:pipe:0",
            "-codec:a",
            "copy",
            "-loglevel",
            "error",
            str(output_path),
        ],
        input=b"".join(lista_mp3),
        check=True,
        timeout=30,
    )


# ─── Riproduzione audio ─────────────────────────────────────────────────────


def _trova_player(formato: str) -> tuple[list[str], bool]:
    """Trova il comando di riproduzione audio per l'OS corrente.

    Parameters
    ----------
    formato : str
        Formato audio: "wav" o "mp3".

    Returns
    -------
    tuple[list[str], bool]
        (comando con argomenti, supporta_stdin). Se supporta_stdin è False,
        il comando richiede un file temporaneo.
    """
    if PLATFORM == "darwin":
        # afplay: nativo macOS, supporta WAV e MP3, ma non stdin
        if shutil.which("afplay"):
            return ["afplay"], False
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-"], True

    elif PLATFORM == "win32":
        # Windows: ffplay è il player principale (incluso in ffmpeg)
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-"], True

    else:
        # Linux: aplay per WAV, ffplay per MP3
        if formato == "wav" and shutil.which("aplay"):
            return ["aplay", "-q", "-"], True
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-"], True

    return [], False


def _ha_player(formato: str) -> bool:
    """Verifica se un player audio è disponibile per il formato sull'OS corrente."""
    cmd, _ = _trova_player(formato)
    return len(cmd) > 0


def riproduci_audio(audio_bytes: bytes, formato: str):
    """Riproduce audio usando il player disponibile sull'OS corrente."""
    cmd, supporta_stdin = _trova_player(formato)
    if not cmd:
        error(f"Nessun player audio trovato per {formato}.")
        error(f"Installa ffmpeg:\n         {suggerisci_installazione('ffmpeg')}")
        return

    if supporta_stdin:
        subprocess.run(cmd, input=audio_bytes, check=False, timeout=60)
    else:
        # afplay (macOS) non supporta stdin: usa file temporaneo
        import tempfile

        ext = f".{formato}"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            subprocess.run([*cmd, tmp_path], check=False, timeout=60)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ─── Lettura con Piper TTS ──────────────────────────────────────────────────


def leggi_con_piper(testo: str, salva_path: Path | None = None, cartella_par: Path | None = None):
    try:
        from piper import PiperVoice
    except ImportError:
        error("Piper non trovato. Installa con: pip install piper-tts")
        sys.exit(1)

    riproduce = _ha_player("wav")
    if not riproduce and salva_path is None:
        installa = suggerisci_installazione("ffmpeg")
        error(f"Nessun player audio trovato.\n         Installa ffmpeg:\n         {installa}")
        sys.exit(1)

    if salva_path and not shutil.which("ffmpeg"):
        error(f"ffmpeg non trovato.\n         {suggerisci_installazione('ffmpeg')}")
        sys.exit(1)

    info("Carico la voce Paola...")
    voce = PiperVoice.load(str(VOICE_MODEL), config_path=str(VOICE_JSON))
    sample_rate = voce.config.sample_rate

    paragrafi = [p.strip() for p in testo.split("\n\n") if p.strip()]
    info(f"Paragrafi da leggere: {len(paragrafi)}")

    if salva_path:
        salva_path.parent.mkdir(parents=True, exist_ok=True)
        if cartella_par:
            cartella_par.mkdir(parents=True, exist_ok=True)
        info(f"Salvataggio in: {salva_path}")

    if riproduce:
        info("Avvio lettura... (Ctrl+C per interrompere)")

    tutti_wav = []

    try:
        for i, paragrafo in enumerate(paragrafi, 1):
            mostra_paragrafo(i, len(paragrafi), paragrafo, riproduce)
            wav_bytes = sintetizza_piper(voce, paragrafo, sample_rate)

            if salva_path:
                tutti_wav.append(wav_bytes)
                if cartella_par:
                    wav_a_mp3(wav_bytes, cartella_par / f"{i:03d}.mp3")
                if not riproduce:
                    info(f"[{i}/{len(paragrafi)}] salvato")

            if riproduce:
                riproduci_audio(wav_bytes, "wav")

    except KeyboardInterrupt:  # pragma: no cover — requires real SIGINT
        print()
        info("Lettura interrotta.")

    if salva_path and tutti_wav:
        info("Creo file audio completo...")
        wav_completo = concatena_wav(tutti_wav, sample_rate)
        wav_a_mp3(wav_completo, salva_path)
        info(f"Salvato: {salva_path} ({len(tutti_wav)} paragrafi)")


# ─── Lettura con Edge TTS ───────────────────────────────────────────────────


def leggi_con_edge(
    testo: str, voice_name: str, salva_path: Path | None = None, cartella_par: Path | None = None
):
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        error("edge-tts non trovato. Installa con: pip install edge-tts")
        sys.exit(1)

    voice_id = EDGE_VOICES[voice_name]["edge_id"]
    riproduce = _ha_player("mp3")
    if not riproduce and salva_path is None:
        installa = suggerisci_installazione("ffmpeg")
        error(f"Nessun player audio trovato.\n         Installa ffmpeg:\n         {installa}")
        sys.exit(1)

    paragrafi = [p.strip() for p in testo.split("\n\n") if p.strip()]
    info(f"Paragrafi da leggere: {len(paragrafi)}")

    if salva_path:
        salva_path.parent.mkdir(parents=True, exist_ok=True)
        if cartella_par:
            cartella_par.mkdir(parents=True, exist_ok=True)
        info(f"Salvataggio in: {salva_path}")

    if riproduce:
        info("Avvio lettura... (Ctrl+C per interrompere)")

    asyncio.run(_loop_edge(voice_id, paragrafi, riproduce, salva_path, cartella_par))


async def _loop_edge(voice_id, paragrafi, riproduce, salva_path, cartella_par):
    tutti_mp3 = []
    totale = len(paragrafi)

    # Prefetch: sintetizza il primo paragrafo subito
    prossimo = asyncio.create_task(sintetizza_edge(voice_id, paragrafi[0]))

    try:
        for i, paragrafo in enumerate(paragrafi, 1):
            mostra_paragrafo(i, totale, paragrafo, riproduce)

            # Attendi l'audio (già in prefetch)
            mp3_bytes = await prossimo

            # Lancia prefetch del prossimo paragrafo durante la riproduzione
            if i < totale:
                prossimo = asyncio.create_task(sintetizza_edge(voice_id, paragrafi[i]))

            if salva_path:
                tutti_mp3.append(mp3_bytes)
                if cartella_par:
                    (cartella_par / f"{i:03d}.mp3").write_bytes(mp3_bytes)
                if not riproduce:
                    info(f"[{i}/{totale}] salvato")

            if riproduce:
                await _riproduci_async(mp3_bytes)

    except KeyboardInterrupt:  # pragma: no cover — requires real SIGINT
        print()
        info("Lettura interrotta.")

    if salva_path and tutti_mp3:
        info("Creo file audio completo...")
        concatena_mp3(tutti_mp3, salva_path)
        info(f"Salvato: {salva_path} ({len(tutti_mp3)} paragrafi)")


async def _riproduci_async(mp3_bytes: bytes):
    """Riproduce MP3 in modo non-bloccante per l'event loop."""
    cmd, supporta_stdin = _trova_player("mp3")
    if not cmd:
        return

    if supporta_stdin:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=mp3_bytes)
    else:
        # afplay (macOS): richiede file temporaneo
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(mp3_bytes)
            tmp_path = tmp.name
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, tmp_path)
            await proc.wait()
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ─── Utilità UI ──────────────────────────────────────────────────────────────


def calcola_path_output(input_file: Path):
    """Calcola le directory di output dalla struttura data/.

    Parameters
    ----------
    input_file : Path
        File sorgente (es. data/input/documento.md).

    Returns
    -------
    tuple[Path, Path, Path]
        (cartella_base, path_mp3_completo, cartella_paragrafi)
        Es: data/output/documento/full/documento.mp3,
            data/output/documento/paragraphs/
    """
    stem = input_file.stem
    cartella_base = DATA_OUTPUT / stem
    cartella_full = cartella_base / "full"
    cartella_par = cartella_base / "paragraphs"
    path_mp3 = cartella_full / f"{stem}.mp3"
    return cartella_base, path_mp3, cartella_par


def mostra_paragrafo(i: int, totale: int, testo: str, visibile: bool):
    if not visibile:
        return
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.write(f"{GREEN}[{i}/{totale}]{NC}\n\n")
    sys.stdout.write(testo + "\n")
    sys.stdout.flush()


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    from src.converters import SUPPORTED_EXTENSIONS, file_a_testo

    ext_list = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    parser = argparse.ArgumentParser(
        description="Legge ad alta voce file di testo in italiano.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""formati supportati: {ext_list}

voci disponibili:
  giuseppe  Edge TTS, maschile, multilingue IT/EN (default)
  isabella  Edge TTS, femminile
  elsa      Edge TTS, femminile
  diego     Edge TTS, maschile
  paola     Piper TTS, femminile, offline

struttura output (con --salva):
  data/output/<nome_file>/full/<nome_file>.mp3
  data/output/<nome_file>/paragraphs/001.mp3, 002.mp3, ...""",
    )
    parser.add_argument("file", type=Path, help="File da leggere")
    parser.add_argument(
        "--voice",
        choices=ALL_VOICES,
        default=DEFAULT_VOICE,
        help=f"Voce da usare (default: {DEFAULT_VOICE})",
    )
    parser.add_argument(
        "--salva",
        action="store_true",
        help="Salva l'audio in data/output/<nome_file>/",
    )
    args = parser.parse_args()

    errori = verifica_prerequisiti(modalita="cli")
    if errori:
        sys.exit(1)

    if not args.file.exists():
        error(f"File non trovato: {args.file}")
        sys.exit(1)

    info(f"File: {args.file.name}")
    info(f"Voce: {args.voice}")

    salva_path = None
    cartella_par = None
    if args.salva:
        _, salva_path, cartella_par = calcola_path_output(args.file)
        info(f"Output: {salva_path.parent.parent}/")

    info("Converto in testo...")
    testo = file_a_testo(args.file)

    if not testo.strip():
        error("Il file sembra vuoto dopo la conversione.")
        sys.exit(1)

    info(f"Testo estratto: {len(testo)} caratteri")

    if args.voice in PIPER_VOICES:
        scarica_voce_piper()
        leggi_con_piper(testo, salva_path=salva_path, cartella_par=cartella_par)
    else:
        leggi_con_edge(testo, args.voice, salva_path=salva_path, cartella_par=cartella_par)

    info("Fine.")


if __name__ == "__main__":  # pragma: no cover
    main()
