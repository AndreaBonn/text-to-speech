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
    from src.app import app, engine

    app.config["TESTING"] = True
    engine._paragraphs = []
    engine._filename = ""
    engine._cache.clear()

    # /api/voices probes the online voices over the network: keep tests offline.
    with patch.object(engine, "is_online_available", return_value=True), app.test_client() as c:
        yield c


@pytest.fixture()
def engine():
    """Crea un TTSEngine fresco per ogni test."""
    from src.tts_engine import TTSEngine

    return TTSEngine()
