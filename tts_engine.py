"""
tts_engine.py
Wrapper TTS con cache in-memory e prefetch asincrono.
Importa le funzioni di sintesi da leggi.py.
"""

import asyncio
import logging
import subprocess
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from converters import file_a_testo
from config import EDGE_VOICES, PIPER_VOICES, VOICE_MODEL, VOICE_JSON
from leggi import sintetizza_edge, sintetizza_piper, scarica_voce_piper

log = logging.getLogger(__name__)

# Event loop dedicato per le coroutine Edge TTS (thread-safe)
_async_loop = asyncio.new_event_loop()
threading.Thread(target=_async_loop.run_forever, daemon=True, name="tts-async-loop").start()

MAX_CACHE = 50
_executor = ThreadPoolExecutor(max_workers=2)


def _wav_to_mp3_bytes(wav_bytes: bytes) -> bytes:
    """Converte WAV in MP3 in memoria tramite ffmpeg (pipe in/out)."""
    result = subprocess.run(
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
            "-f",
            "mp3",
            "pipe:1",
        ],
        input=wav_bytes,
        capture_output=True,
        check=True,
        timeout=30,
    )
    return result.stdout


def _concat_mp3_bytes(mp3_list: list[bytes]) -> bytes:
    """Concatena una lista di MP3 in un unico file.

    I frame MP3 sono auto-sincronizzanti: la concatenazione
    diretta dei bytes produce un file valido senza re-encoding.
    """
    return b"".join(mp3_list)


class TTSEngine:
    """Gestisce sintesi, cache e prefetch per la web UI."""

    def __init__(self):
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()
        self._paragraphs: list[str] = []
        self._filename: str = ""
        self._piper_voice = None
        self._piper_sample_rate: int = 0

    @property
    def paragraphs(self) -> list[str]:
        return self._paragraphs

    @property
    def filename(self) -> str:
        return self._filename

    def load_file(self, path: Path) -> list[str]:
        """Carica un file e restituisce la lista di paragrafi.

        Supporta: .md, .txt, .epub, .docx, .html, .htm, .pdf
        """
        testo = file_a_testo(path)
        paragraphs = [p.strip() for p in testo.split("\n\n") if p.strip()]
        with self._lock:
            self._paragraphs = paragraphs
            self._filename = path.name
            self._cache.clear()
        return paragraphs

    def load_text(self, text: str, filename: str) -> list[str]:
        """Carica testo raw e restituisce la lista di paragrafi."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        with self._lock:
            self._paragraphs = paragraphs
            self._filename = filename
            self._cache.clear()
        return paragraphs

    def get_audio(self, index: int, voice: str) -> bytes:
        """Restituisce MP3 bytes per il paragrafo. Usa cache se disponibile."""
        if index < 0 or index >= len(self._paragraphs):
            raise IndexError(f"Paragrafo {index} fuori range")

        cache_key = f"{voice}:{index}"
        with self._lock:
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]

        mp3_bytes = self._synthesize(index, voice)
        self._put_cache(cache_key, mp3_bytes)

        # Prefetch prossimo paragrafo in background
        if index + 1 < len(self._paragraphs):
            self.prefetch(index + 1, voice)

        return mp3_bytes

    def prefetch(self, index: int, voice: str):
        """Lancia sintesi del paragrafo in background (thread pool)."""
        if index < 0 or index >= len(self._paragraphs):
            return
        cache_key = f"{voice}:{index}"
        with self._lock:
            if cache_key in self._cache:
                return

        def _do_prefetch():
            try:
                mp3 = self._synthesize(index, voice)
                self._put_cache(cache_key, mp3)
            except Exception:
                log.warning("Prefetch paragrafo %d fallito", index, exc_info=True)

        _executor.submit(_do_prefetch)

    def save_all(self, voice: str) -> bytes:
        """Sintetizza tutti i paragrafi e restituisce MP3 concatenato.

        Usa uno snapshot della lista paragrafi per evitare corruzione
        se un nuovo file viene caricato durante l'operazione.
        """
        with self._lock:
            snapshot = list(self._paragraphs)

        all_mp3 = []
        for i in range(len(snapshot)):
            all_mp3.append(self.get_audio(i, voice))
        return _concat_mp3_bytes(all_mp3)

    def _synthesize(self, index: int, voice: str) -> bytes:
        """Sintetizza un paragrafo. Restituisce sempre MP3."""
        text = self._paragraphs[index]

        if voice in EDGE_VOICES:
            voice_id = EDGE_VOICES[voice]
            future = asyncio.run_coroutine_threadsafe(sintetizza_edge(voice_id, text), _async_loop)
            return future.result(timeout=60)

        # Piper (offline) — carica il modello lazy
        if self._piper_voice is None:
            self._load_piper()

        wav_bytes = sintetizza_piper(self._piper_voice, text, self._piper_sample_rate)
        return _wav_to_mp3_bytes(wav_bytes)

    def _load_piper(self):
        """Carica il modello Piper una sola volta (thread-safe)."""
        with self._lock:
            if self._piper_voice is not None:
                return
            from piper import PiperVoice

            scarica_voce_piper()
            self._piper_voice = PiperVoice.load(str(VOICE_MODEL), config_path=str(VOICE_JSON))
            self._piper_sample_rate = self._piper_voice.config.sample_rate

    def _put_cache(self, key: str, data: bytes):
        with self._lock:
            self._cache[key] = data
            while len(self._cache) > MAX_CACHE:
                self._cache.popitem(last=False)

    def _clear_cache(self):
        with self._lock:
            self._cache.clear()
