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

from src.chapters import trova_capitoli, unisci_con_capitoli
from src.config import DEFAULT_STYLE, EDGE_VOICES, READING_STYLES, VOICE_JSON, VOICE_MODEL
from src.converters import file_a_testo
from src.synthesis import scarica_voce_piper, sintetizza_edge, sintetizza_piper
from src.titles import estrai_titoli

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
        self._probe_lock = threading.Lock()
        # Syntheses running now, by (generation, cache key): later requests join them.
        self._inflight: dict[tuple[int, str], concurrent.futures.Future] = {}
        self._paragraphs: list[str] = []
        # (paragraph index, title) for the ID3 chapters of the saved MP3.
        self._chapters: list[tuple[int, str]] = []
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
        chapters = trova_capitoli(paragrafi=paragraphs, titoli=estrai_titoli(path))
        with self._lock:
            self._paragraphs = paragraphs
            self._chapters = chapters
            self._generation += 1
            self._filename = display_name or path.name
            self._cache.clear()
        return paragraphs

    def load_text(self, text: str, filename: str) -> list[str]:
        """Carica testo raw e restituisce la lista di paragrafi."""
        paragraphs = _split_paragraphs(text)
        with self._lock:
            self._paragraphs = paragraphs
            self._chapters = []
            self._generation += 1
            self._filename = filename
            self._cache.clear()
        return paragraphs

    def get_audio(self, index: int, voice: str, style: str = DEFAULT_STYLE) -> bytes:
        """Restituisce MP3 bytes per il paragrafo. Usa cache se disponibile."""
        text, generation = self._paragraph_at(index)
        cache_key = f"{voice}:{style}:{index}"
        mp3_bytes = self._cached_or_synthesize(
            cache_key, generation, lambda: self._synthesize_text(text, voice, style)
        )

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
        cache_key = f"{voice}:{style}:{index}"
        with self._lock:
            # Range checked under the lock: a load may shorten the document.
            if index < 0 or index >= len(self._paragraphs):
                return
            generation = self._generation
            if cache_key in self._cache or (generation, cache_key) in self._inflight:
                return
            text = self._paragraphs[index]

        def _do_prefetch():
            try:
                self._cached_or_synthesize(
                    cache_key, generation, lambda: self._synthesize_text(text, voice, style)
                )
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

        Se il documento ha titoli, l'MP3 porta un capitolo ID3 per titolo.

        Usa uno snapshot della lista paragrafi per evitare corruzione
        se un nuovo file viene caricato durante l'operazione.
        ``on_progress(done, total)`` viene chiamato all'inizio e dopo ogni paragrafo.
        """
        with self._lock:
            snapshot = list(self._paragraphs)
            chapters = list(self._chapters)
            generation = self._generation

        total = len(snapshot)
        report = on_progress or (lambda done, total: None)
        report(0, total)
        all_mp3 = []
        for i, text in enumerate(snapshot):
            all_mp3.append(self._snapshot_audio(i, text, voice, style, generation))
            report(i + 1, total)
        return unisci_con_capitoli(segmenti=all_mp3, capitoli=chapters)

    def _snapshot_audio(
        self, index: int, text: str, voice: str, style: str, generation: int
    ) -> bytes:
        """Audio of a snapshot paragraph: cached only while its document is current.

        The text always comes from the snapshot, never from ``self._paragraphs``
        by index: a document loaded mid-save would otherwise leak its paragraphs
        (or an IndexError) into the file being saved.
        """
        cache_key = f"{voice}:{style}:{index}"
        return self._cached_or_synthesize(
            cache_key, generation, lambda: self._synthesize_text(text, voice, style)
        )

    def _cached_or_synthesize(
        self, cache_key: str, generation: int, synthesize: Callable[[], bytes]
    ) -> bytes:
        """Cached audio, else join the synthesis already running for it, else run it.

        A request for a paragraph that the prefetch is synthesizing waits for
        that synthesis instead of sending Edge the same text a second time.
        """
        flight_key = (generation, cache_key)
        with self._lock:
            if generation == self._generation and cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]
            pending = self._inflight.get(flight_key)
            owner = pending is None
            if owner:
                pending = self._inflight[flight_key] = concurrent.futures.Future()
        if not owner:
            return pending.result()
        try:
            mp3_bytes = synthesize()
        except BaseException as err:
            pending.set_exception(err)
            raise
        else:
            # Waiters first: they must never hang on a failure while caching.
            pending.set_result(mp3_bytes)
            self._put_cache_if_current(cache_key, mp3_bytes, generation)
            return mp3_bytes
        finally:
            with self._lock:
                self._inflight.pop(flight_key, None)

    def _paragraph_at(self, index: int) -> tuple[str, int]:
        """Text of a paragraph and the generation it belongs to, read together.

        Read in two lock sections, a load in between paired the new document's
        text with the old generation (or the reverse) for that request.
        """
        with self._lock:
            if index < 0 or index >= len(self._paragraphs):
                raise IndexError(f"Paragrafo {index} fuori range")
            return self._paragraphs[index], self._generation

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
        """Verifica (con cache) che le voci online rispondano.

        Una sola verifica alla volta: chi arriva durante la verifica aspetta e
        riusa il risultato appena salvato, invece di lanciarne un'altra.
        """
        with self._probe_lock:
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
