"""
tests/conftest.py
Fixture condivise per la test suite.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Assicura che la root del progetto sia nel path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def client():
    """Flask test client con engine resettato a ogni test."""
    from src.app import _set_save_progress, app, engine

    app.config["TESTING"] = True
    # load_text() clears the cache, bumps the generation (so in-flight prefetches from
    # a previous test cannot write into this one) and resets the filename. The engine
    # has no public "unload" and rejects empty text, so the paragraphs are emptied directly.
    engine.load_text("reset", "")
    engine._paragraphs = []
    _set_save_progress(0, 0, active=False)

    # /api/voices probes the online voices over the network: keep tests offline.
    with patch.object(engine, "is_online_available", return_value=True), app.test_client() as c:
        yield c


@pytest.fixture()
def engine():
    """Crea un TTSEngine fresco per ogni test."""
    from src.tts_engine import TTSEngine

    return TTSEngine()


@pytest.fixture(scope="session")
def sine_mp3():
    """Factory: MP3 mono 24 kHz 48 kbit/s come quelli di Edge TTS, generato da ffmpeg."""

    def _make(durata_s: float, freq: int = 440) -> bytes:
        return subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={freq}:duration={durata_s}",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "48k",
                "-f",
                "mp3",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
        ).stdout

    return _make


@pytest.fixture()
def ffprobe_mp3(tmp_path):
    """Factory: capitoli e durata di un MP3 (bytes o path) come li vede ffprobe."""

    def _probe(mp3: bytes | Path) -> dict:
        path = mp3 if isinstance(mp3, Path) else tmp_path / "probe.mp3"
        if not isinstance(mp3, Path):
            path.write_bytes(mp3)
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_chapters", "-show_format", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        info = json.loads(out)
        return {
            "titoli": [c["tags"]["title"] for c in info["chapters"]],
            "inizi": [float(c["start_time"]) for c in info["chapters"]],
            "fine": float(info["chapters"][-1]["end_time"]) if info["chapters"] else None,
            "durata": float(info["format"]["duration"]),
        }

    return _probe


def pytest_collection_modifyitems(items):
    """Run the browser tests last.

    Playwright's sync API keeps an asyncio event loop running in the main thread
    for the rest of the session: any later test calling asyncio.run() fails with
    "cannot be called from a running event loop".
    """
    items.sort(key=lambda item: "e2e" in item.path.parts)
