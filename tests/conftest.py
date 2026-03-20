"""
tests/conftest.py
Fixture condivise per la test suite.
"""

import sys
from pathlib import Path

import pytest

# Assicura che la root del progetto sia nel path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def client():
    """Flask test client con engine resettato a ogni test."""
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    flask_app.engine._paragraphs = []
    flask_app.engine._filename = ""
    flask_app.engine._cache.clear()

    with flask_app.app.test_client() as c:
        yield c


@pytest.fixture()
def engine():
    """Crea un TTSEngine fresco per ogni test."""
    from tts_engine import TTSEngine

    return TTSEngine()
