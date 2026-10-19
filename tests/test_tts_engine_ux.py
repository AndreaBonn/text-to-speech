"""
tests/test_tts_engine_ux.py
Engine behaviors needed by the web UI: rejecting documents without text
without losing the document that is currently loaded.
"""

from unittest.mock import patch

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


class TestOnlineProbe:
    def test_probe_reports_unavailable_when_synthesis_fails(self, engine):
        with patch.object(engine, "_synthesize_text", side_effect=OSError("403")):
            assert engine.is_online_available() is False

    def test_probe_reports_available_when_synthesis_works(self, engine):
        with patch.object(engine, "_synthesize_text", return_value=b"mp3"):
            assert engine.is_online_available() is True

    def test_probe_result_is_cached_between_calls(self, engine):
        with patch.object(engine, "_synthesize_text", return_value=b"mp3") as synth:
            engine.is_online_available()
            engine.is_online_available()

        assert synth.call_count == 1
