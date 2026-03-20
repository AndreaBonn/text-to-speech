"""
synthesis.py
Funzioni di sintesi vocale: Piper TTS (offline), Edge TTS (online), download modelli.

Questo modulo è importato sia dal web server (tts_engine.py) sia dalla CLI (leggi.py).
Non deve mai chiamare sys.exit() — gli errori sono segnalati tramite eccezioni.
"""

import io
import urllib.request
import wave
from pathlib import Path

from config import (
    VOICE_DIR,
    VOICE_URLS,
    info,
    warn,
    error,
)


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
            with urllib.request.urlopen(url) as response, open(dest, "wb") as f:
                total = int(response.headers.get("Content-Length", 0))
                scaricati = 0
                while True:
                    chunk = response.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)
                    scaricati += len(chunk)
                    if total:
                        print(f"\r  {scaricati/total*100:.1f}%", end="", flush=True)
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


async def sintetizza_edge(voice_id: str, testo: str) -> bytes:
    """Sintetizza testo con Edge TTS (Microsoft, richiede internet).

    Parameters
    ----------
    voice_id : str
        Identificativo voce Edge TTS (es. "it-IT-GiuseppeMultilingualNeural").
    testo : str
        Testo da sintetizzare.

    Returns
    -------
    bytes
        Audio MP3 in memoria.
    """
    import edge_tts

    comm = edge_tts.Communicate(testo, voice_id)
    buf = io.BytesIO()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()
