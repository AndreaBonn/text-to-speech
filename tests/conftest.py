"""
tests/conftest.py
Fixture condivise per la test suite.
"""

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


def pytest_collection_modifyitems(items):
    """Run the browser tests last.

    Playwright's sync API keeps an asyncio event loop running in the main thread
    for the rest of the session: any later test calling asyncio.run() fails with
    "cannot be called from a running event loop".
    """
    items.sort(key=lambda item: "e2e" in item.path.parts)
