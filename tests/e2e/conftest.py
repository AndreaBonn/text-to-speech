"""
tests/e2e/conftest.py
End-to-end fixtures: the real Flask app served on a free port, driven by a real
Chromium through pytest-playwright. Only speech synthesis is faked, at the
engine boundary, with a real 1-second MP3 so the <audio> element can play it.
"""

import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from unittest.mock import patch

import pytest
from werkzeug.serving import make_server


@dataclass
class LiveApp:
    """URL of the running app and the synthesis calls it received."""

    url: str
    synth_calls: list[tuple[str, str, str]] = field(default_factory=list)


def _drain_prefetch_executor() -> None:
    """Wait for the prefetches the page started, while synthesis is still faked.

    A prefetch finishing after the patch is removed would call the real
    synthesis (Edge over the network). With every worker parked on a barrier,
    all tasks queued before it have completed: the queue is FIFO.
    """
    from src.tts_engine import _executor

    workers = _executor._max_workers
    barrier = threading.Barrier(workers + 1)
    for _ in range(workers):
        _executor.submit(barrier.wait, 10)
    barrier.wait(10)


@pytest.fixture(scope="session")
def short_mp3(tmp_path_factory) -> bytes:
    """A real 1 s MP3, so the browser decodes and plays it like Edge/Piper audio."""
    if shutil.which("ffmpeg") is None:
        pytest.fail("ffmpeg is required for the e2e tests (it is a project dependency)")
    out = tmp_path_factory.mktemp("audio") / "short.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-codec:a",
            "libmp3lame",
            str(out),
        ],
        check=True,
    )
    return out.read_bytes()


@pytest.fixture()
def live_app(short_mp3):
    """Serve src.app on 127.0.0.1 with a fresh engine and fake synthesis."""
    from src.app import _set_save_progress, app, engine

    engine._paragraphs = []
    engine.load_text("reset", "")
    engine._paragraphs = []
    _set_save_progress(0, 0, active=False)

    live = LiveApp(url="")

    def fake_synthesize_text(text, voice, style="neutro", timeout=None):
        live.synth_calls.append((text, voice, style))
        return short_mp3

    server = make_server("127.0.0.1", 0, app, threaded=True)
    live.url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    with (
        patch.object(engine, "_synthesize_text", side_effect=fake_synthesize_text),
        patch.object(engine, "is_online_available", return_value=True),
    ):
        thread.start()
        try:
            yield live
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)
            _drain_prefetch_executor()


@pytest.fixture()
def reader(page, live_app):
    """Page object of the reader, already pointed at the live app."""
    from tests.e2e.reader_page import ReaderPage

    return ReaderPage(page, live_app.url)
