"""
tts_engine.py
Wrapper TTS con cache in-memory e prefetch asincrono.
Importa le funzioni di sintesi da synthesis.py.
"""

import asyncio
import concurrent.futures
import logging
import subprocess
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.config import DEFAULT_STYLE, EDGE_VOICES, READING_STYLES, VOICE_JSON, VOICE_MODEL
from src.converters import file_a_testo
from src.synthesis import scarica_voce_piper, sintetizza_edge, sintetizza_piper

log = logging.getLogger(__name__)

# Event loop dedicato per le coroutine Edge TTS (thread-safe)
_async_loop = asyncio.new_event_loop()
threading.Thread(target=_async_loop.run_forever, daemon=True, name="tts-async-loop").start()

MAX_CACHE = 50
SYNTHESIS_TIMEOUT_S = 60
# The online check runs on page load: short timeout, result reused for a few minutes.
ONLINE_PROBE_TIMEOUT_S = 8
ONLINE_PROBE_TTL_S = 300
# A failed check is retried soon: one network hiccup must not switch every page
# load to the offline voice for minutes (observed once during testing).
ONLINE_PROBE_FAILURE_TTL_S = 30
ONLINE_PROBE_VOICE = next(iter(EDGE_VOICES))
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


class EmptyDocumentError(ValueError):
    """Il documento non contiene testo leggibile (file vuoto, PDF solo immagini)."""


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        raise EmptyDocumentError("no readable text")
    return paragraphs


class TTSEngine:
    """Gestisce sintesi, cache e prefetch per la web UI."""

    def __init__(self):
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()
        # Separate from _lock: the first Piper use downloads ~60 MB, and holding
        # the cache/document lock that long would freeze every request.
        self._piper_lock = threading.Lock()
        self._paragraphs: list[str] = []
        self._filename: str = ""
        self._piper_voice = None
        self._piper_sample_rate: int = 0
        self._online_ok = False
        # Bumped on every load: audio synthesized for an older document must not
        # land in the cache under the new document's paragraph keys.
        self._generation = 0
        self._online_checked_at: float | None = None

    @property
    def paragraphs(self) -> list[str]:
        return self._paragraphs

    @property
    def filename(self) -> str:
        return self._filename

    def load_file(self, path: Path, display_name: str | None = None) -> list[str]:
        """Carica un file e restituisce la lista di paragrafi.

        Supporta: .md, .txt, .epub, .docx, .html, .htm, .pdf. ``display_name`` è il
        nome originale del documento quando ``path`` è un file temporaneo.
        """
        paragraphs = _split_paragraphs(file_a_testo(path))
        with self._lock:
            self._paragraphs = paragraphs
            self._generation += 1
            self._filename = display_name or path.name
            self._cache.clear()
        return paragraphs

    def load_text(self, text: str, filename: str) -> list[str]:
        """Carica testo raw e restituisce la lista di paragrafi."""
        paragraphs = _split_paragraphs(text)
        with self._lock:
            self._paragraphs = paragraphs
            self._generation += 1
            self._filename = filename
            self._cache.clear()
        return paragraphs

    def get_audio(self, index: int, voice: str, style: str = DEFAULT_STYLE) -> bytes:
        """Restituisce MP3 bytes per il paragrafo. Usa cache se disponibile."""
        if index < 0 or index >= len(self._paragraphs):
            raise IndexError(f"Paragrafo {index} fuori range")

        cache_key = f"{voice}:{style}:{index}"
        with self._lock:
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]

        generation = self._generation
        mp3_bytes = self._synthesize(index, voice, style)
        self._put_cache_if_current(cache_key, mp3_bytes, generation)

        # Prefetch prossimo paragrafo in background
        if index + 1 < len(self._paragraphs):
            self.prefetch(index + 1, voice, style)

        return mp3_bytes

    def get_preview(self, text: str, voice: str, style: str = DEFAULT_STYLE) -> bytes:
        """MP3 di una frase di prova per la voce, indipendente dal documento caricato."""
        cache_key = f"preview:{voice}:{style}"
        with self._lock:
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]
        mp3_bytes = self._synthesize_text(text, voice, style)
        self._put_cache(cache_key, mp3_bytes)
        return mp3_bytes

    def prefetch(self, index: int, voice: str, style: str = DEFAULT_STYLE):
        """Lancia sintesi del paragrafo in background (thread pool)."""
        if index < 0 or index >= len(self._paragraphs):
            return
        cache_key = f"{voice}:{style}:{index}"
        with self._lock:
            if cache_key in self._cache:
                return

        generation = self._generation

        def _do_prefetch():
            try:
                mp3 = self._synthesize(index, voice, style)
                self._put_cache_if_current(cache_key, mp3, generation)
            except Exception:
                log.warning("Prefetch paragrafo %d fallito", index, exc_info=True)

        return _executor.submit(_do_prefetch)

    def save_all(
        self,
        voice: str,
        style: str = DEFAULT_STYLE,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> bytes:
        """Sintetizza tutti i paragrafi e restituisce MP3 concatenato.

        Usa uno snapshot della lista paragrafi per evitare corruzione
        se un nuovo file viene caricato durante l'operazione.
        ``on_progress(done, total)`` viene chiamato all'inizio e dopo ogni paragrafo.
        """
        with self._lock:
            snapshot = list(self._paragraphs)
            generation = self._generation

        total = len(snapshot)
        report = on_progress or (lambda done, total: None)
        report(0, total)
        all_mp3 = []
        for i, text in enumerate(snapshot):
            all_mp3.append(self._snapshot_audio(i, text, voice, style, generation))
            report(i + 1, total)
        return _concat_mp3_bytes(all_mp3)

    def _snapshot_audio(
        self, index: int, text: str, voice: str, style: str, generation: int
    ) -> bytes:
        """Audio of a snapshot paragraph: cached only while its document is current.

        The text always comes from the snapshot, never from ``self._paragraphs``
        by index: a document loaded mid-save would otherwise leak its paragraphs
        (or an IndexError) into the file being saved.
        """
        cache_key = f"{voice}:{style}:{index}"
        with self._lock:
            if generation == self._generation and cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]
        mp3_bytes = self._synthesize_text(text, voice, style)
        self._put_cache_if_current(cache_key, mp3_bytes, generation)
        return mp3_bytes

    def _synthesize(self, index: int, voice: str, style: str = DEFAULT_STYLE) -> bytes:
        """Sintetizza un paragrafo. Restituisce sempre MP3."""
        with self._lock:
            if index < 0 or index >= len(self._paragraphs):
                raise IndexError(f"Paragrafo {index} fuori range (durante sintesi)")
            text = self._paragraphs[index]
        return self._synthesize_text(text, voice, style)

    def _synthesize_text(
        self,
        text: str,
        voice: str,
        style: str = DEFAULT_STYLE,
        timeout: float = SYNTHESIS_TIMEOUT_S,
    ) -> bytes:
        """Sintetizza un testo arbitrario. Restituisce sempre MP3."""
        if voice in EDGE_VOICES:
            voice_id = EDGE_VOICES[voice]["edge_id"]
            params = READING_STYLES.get(style, READING_STYLES[DEFAULT_STYLE])
            future = asyncio.run_coroutine_threadsafe(
                sintetizza_edge(voice_id, text, rate=params["rate"], pitch=params["pitch"]),
                _async_loop,
            )
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                # Without this the coroutine keeps running in the loop: one
                # abandoned synthesis per timeout (e.g. every failed online probe).
                future.cancel()
                raise

        # Piper (offline) — carica il modello lazy, stile ignorato
        if self._piper_voice is None:
            self._load_piper()

        wav_bytes = sintetizza_piper(self._piper_voice, text, self._piper_sample_rate)
        return _wav_to_mp3_bytes(wav_bytes)

    def is_online_available(self) -> bool:
        """Verifica (con cache) che le voci online rispondano."""
        now = time.monotonic()
        ttl = ONLINE_PROBE_TTL_S if self._online_ok else ONLINE_PROBE_FAILURE_TTL_S
        if self._online_checked_at is not None and now - self._online_checked_at < ttl:
            return self._online_ok
        try:
            self._synthesize_text("ok", ONLINE_PROBE_VOICE, timeout=ONLINE_PROBE_TIMEOUT_S)
            ok = True
        except Exception:
            log.warning("Voci online non raggiungibili", exc_info=True)
            ok = False
        self._online_ok, self._online_checked_at = ok, now
        return ok

    def _load_piper(self):
        """Carica il modello Piper una sola volta (thread-safe)."""
        with self._piper_lock:
            if self._piper_voice is not None:
                return
            from piper import PiperVoice

            scarica_voce_piper()
            voice = PiperVoice.load(str(VOICE_MODEL), config_path=str(VOICE_JSON))
            # _synthesize_text checks _piper_voice without the lock: publish the
            # voice last, so a reader that sees it also sees its sample rate.
            self._piper_sample_rate = voice.config.sample_rate
            self._piper_voice = voice

    def _put_cache_if_current(self, key: str, data: bytes, generation: int):
        # Check and insert under one lock: a load between them would let audio
        # of the previous document into the new one's cache.
        with self._lock:
            if generation == self._generation:
                self._insert_cache_locked(key, data)

    def _put_cache(self, key: str, data: bytes):
        with self._lock:
            self._insert_cache_locked(key, data)

    def _insert_cache_locked(self, key: str, data: bytes):
        self._cache[key] = data
        while len(self._cache) > MAX_CACHE:
            self._cache.popitem(last=False)

    def _clear_cache(self):
        with self._lock:
            self._cache.clear()
