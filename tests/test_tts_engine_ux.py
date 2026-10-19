"""
tests/test_tts_engine_ux.py
Engine behaviors needed by the web UI: rejecting documents without text
without losing the document that is currently loaded.
"""

import pytest

from src.tts_engine import EmptyDocumentError


class TestLoadWithoutText:
    def test_load_text_without_text_raises_and_keeps_previous_document(self, engine):
        engine.load_text("Primo.\n\nSecondo.", "libro.txt")

        with pytest.raises(EmptyDocumentError):
            engine.load_text("  \n\n ", "vuoto.txt")

        assert engine.paragraphs == ["Primo.", "Secondo."]
        assert engine.filename == "libro.txt"

    def test_load_file_without_text_raises_and_keeps_previous_document(self, engine, tmp_path):
        engine.load_text("Primo.", "libro.txt")
        empty = tmp_path / "vuoto.txt"
        empty.write_text("", encoding="utf-8")

        with pytest.raises(EmptyDocumentError):
            engine.load_file(empty)

        assert engine.paragraphs == ["Primo."]
