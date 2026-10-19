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


class TestSaveProgress:
    def test_save_all_reports_progress_after_each_paragraph(self, engine):
        engine.load_text("Uno.\n\nDue.\n\nTre.", "x.txt")
        steps = []
        with patch.object(engine, "_synthesize_text", return_value=b"mp3"):
            engine.save_all("paola", on_progress=lambda done, total: steps.append((done, total)))

        assert steps == [(0, 3), (1, 3), (2, 3), (3, 3)]


class TestOnlineProbeCacheDuration:
    def test_failed_probe_is_retried_after_a_short_time(self, engine):
        with (
            patch("src.tts_engine.time") as clock,
            patch.object(engine, "_synthesize_text", side_effect=[OSError("timeout"), b"mp3"]),
        ):
            clock.monotonic.side_effect = [1000.0, 1031.0]
            first = engine.is_online_available()
            second = engine.is_online_available()

        assert (first, second) == (False, True)

    def test_successful_probe_is_kept_for_minutes(self, engine):
        with (
            patch("src.tts_engine.time") as clock,
            patch.object(engine, "_synthesize_text", return_value=b"mp3") as synth,
        ):
            clock.monotonic.side_effect = [1000.0, 1299.0]
            engine.is_online_available()
            engine.is_online_available()

        assert synth.call_count == 1


class TestStaleSynthesisAfterNewDocument:
    def test_prefetch_of_previous_document_does_not_poison_new_one(self, engine):
        import threading

        engine.load_text("Vecchio uno.\n\nVecchio due.", "vecchio.txt")
        started, release = threading.Event(), threading.Event()

        def slow_synth(text, voice, style="neutro", timeout=60):
            if text == "Vecchio due.":
                started.set()
                release.wait(5)
            return text.encode()

        from concurrent.futures import ThreadPoolExecutor

        # Own executor: the module one may still be busy with other tests' prefetches
        with (
            patch("src.tts_engine._executor", ThreadPoolExecutor(max_workers=1)),
            patch.object(engine, "_synthesize_text", side_effect=slow_synth),
        ):
            pending = engine.prefetch(1, "paola")
            assert started.wait(5)
            engine.load_text("Nuovo uno.\n\nNuovo due.", "nuovo.txt")
            release.set()
            pending.result(timeout=5)
            audio = engine.get_audio(1, "paola")

        assert audio == b"Nuovo due."

    def test_save_all_finishes_from_snapshot_when_a_new_document_is_loaded(self, engine):
        engine.load_text("Vecchio uno.\n\nVecchio due.", "vecchio.txt")

        def synth(text, voice, style="neutro", timeout=60):
            if text == "Vecchio uno.":
                engine.load_text("Nuovo.", "nuovo.txt")  # loaded while saving
            return text.encode()

        with patch.object(engine, "_synthesize_text", side_effect=synth):
            audio = engine.save_all("paola")

        assert audio == b"Vecchio uno.Vecchio due."
