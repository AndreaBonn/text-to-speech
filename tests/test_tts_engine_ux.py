"""
tests/test_tts_engine_ux.py
Engine behaviors needed by the web UI: rejecting documents without text
without losing the document that is currently loaded.
"""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tts_engine import EmptyDocumentError


@pytest.fixture(autouse=True)
def executor_finto(monkeypatch):
    """Nessun prefetch reale nell'executor di modulo (get_audio lo lancia di default)."""
    monkeypatch.setattr("src.tts_engine._executor", MagicMock())


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


class TestOnlineProbeVoiceAndFailureCache:
    def test_probe_uses_an_online_voice(self, engine):
        from src.config import EDGE_VOICES

        with patch.object(engine, "_synthesize_text", return_value=b"mp3") as synth:
            engine.is_online_available()

        voice = synth.call_args.args[1]
        assert voice in EDGE_VOICES
        assert voice != "paola"

    def test_failed_probe_still_cached_is_not_repeated(self, engine):
        with (
            patch("src.tts_engine.time") as clock,
            patch.object(engine, "_synthesize_text", side_effect=OSError("down")) as synth,
        ):
            clock.monotonic.side_effect = [1000.0, 1010.0]
            first = engine.is_online_available()
            second = engine.is_online_available()

        assert (first, second) == (False, False)
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


class TestSaveAllConsistency:
    """save_all works on its snapshot: no extra syntheses, no cross-document cache."""

    def test_save_all_does_not_prefetch_paragraphs_it_is_about_to_synthesize(
        self, engine, executor_finto
    ):
        import src.tts_engine as tts_engine

        engine.load_text("Uno.\n\nDue.\n\nTre.", "x.txt")

        with patch.object(engine, "_synthesize_text", side_effect=lambda t, v, s: t.encode()):
            audio = engine.save_all("paola")

        assert audio == b"Uno.Due.Tre."
        tts_engine._executor.submit.assert_not_called()

    def test_save_all_fills_the_cache_of_the_current_document(self, engine):
        engine.load_text("Uno.\n\nDue.", "x.txt")

        with patch.object(engine, "_synthesize_text", side_effect=lambda t, v, s: t.encode()):
            engine.save_all("paola", "lento")

        assert engine._cache == {"paola:lento:0": b"Uno.", "paola:lento:1": b"Due."}

    def test_load_during_save_keeps_old_audio_out_of_the_new_cache(self, engine):
        engine.load_text("Vecchio uno.\n\nVecchio due.", "vecchio.txt")

        def synth(text, voice, style="neutro"):
            if text == "Vecchio uno.":
                engine.load_text("Nuovo uno.\n\nNuovo due.", "nuovo.txt")
            return text.encode()

        with patch.object(engine, "_synthesize_text", side_effect=synth):
            audio = engine.save_all("paola")

        assert audio == b"Vecchio uno.Vecchio due."
        assert engine.paragraphs == ["Nuovo uno.", "Nuovo due."]
        assert engine._cache == {}

    def test_save_never_uses_the_new_document_cached_audio(self, engine):
        engine.load_text("Vecchio uno.\n\nVecchio due.", "vecchio.txt")

        def synth(text, voice, style="neutro"):
            if text == "Vecchio uno.":
                engine.load_text("Nuovo uno.\n\nNuovo due.", "nuovo.txt")
                engine._put_cache("paola:neutro:1", b"Nuovo due.")  # played meanwhile
            return text.encode()

        with patch.object(engine, "_synthesize_text", side_effect=synth):
            audio = engine.save_all("paola")

        assert audio == b"Vecchio uno.Vecchio due."
        assert engine._cache == {"paola:neutro:1": b"Nuovo due."}


class TestSynthesisStartedOnPreviousDocument:
    """get_audio iniziato sul documento A e finito dopo il caricamento di B."""

    @staticmethod
    def _load_new(engine, how):
        if how == "text":
            engine.load_text("Nuovo uno.\n\nNuovo due.", "nuovo.txt")
        else:
            with patch("src.tts_engine.file_a_testo", return_value="Nuovo uno.\n\nNuovo due."):
                engine.load_file(Path("/fake/nuovo.txt"))

    @pytest.mark.parametrize("how", ["text", "file"])
    def test_get_audio_finished_after_new_load_does_not_poison_new_document(self, engine, how):
        engine.load_text("Vecchio uno.\n\nVecchio due.", "vecchio.txt")
        started, release = threading.Event(), threading.Event()

        def synth(text, voice, style="neutro", timeout=60):
            if text == "Vecchio uno.":
                started.set()
                release.wait(5)
            return text.encode()

        results = []
        with patch.object(engine, "_synthesize_text", side_effect=synth):
            worker = threading.Thread(target=lambda: results.append(engine.get_audio(0, "paola")))
            worker.start()
            assert started.wait(5)
            self._load_new(engine, how)
            release.set()
            worker.join(5)
            assert not worker.is_alive()
            audio = engine.get_audio(0, "paola")

        assert results == [b"Vecchio uno."]
        assert audio == b"Nuovo uno."

    def test_get_audio_without_new_load_is_cached(self, engine):
        engine.load_text("Uno.\n\nDue.", "x.txt")

        with patch.object(engine, "_synthesize_text", return_value=b"mp3") as synth:
            engine.get_audio(0, "paola")
            engine.get_audio(0, "paola")

        assert synth.call_count == 1


class TestLoadFileDisplayName:
    def test_display_name_replaces_temporary_file_name(self, engine):
        with patch("src.tts_engine.file_a_testo", return_value="Testo."):
            engine.load_file(Path("upload_8f3a.txt"), display_name="relazione.pdf")

        assert engine.filename == "relazione.pdf"


class TestEdgeReturnsNoAudio:
    """Edge that answers without audio: an error, never a silent cached MP3."""

    @staticmethod
    def _edge_without_audio():
        modulo = MagicMock()

        async def stream():
            yield {"type": "WordBoundary", "offset": 0}

        modulo.Communicate.return_value.stream = stream
        return modulo

    def test_get_audio_raises_and_caches_nothing(self, engine):
        engine.load_text("Uno.", "x.txt")

        with (
            patch.dict("sys.modules", {"edge_tts": self._edge_without_audio()}),
            pytest.raises(RuntimeError, match="no audio"),
        ):
            engine.get_audio(0, "giuseppe")

        assert engine._cache == {}

    def test_probe_reports_offline(self, engine):
        with patch.dict("sys.modules", {"edge_tts": self._edge_without_audio()}):
            assert engine.is_online_available() is False


class TestPiperFirstLoadConcurrency:
    """First Piper use downloads ~60 MB: the rest of the engine must keep working."""

    @staticmethod
    def _piper_module(voice):
        modulo = MagicMock()
        modulo.PiperVoice.load.return_value = voice
        return modulo

    def test_engine_stays_usable_while_the_piper_model_downloads(self, engine):
        download_started, release_download = threading.Event(), threading.Event()

        def slow_download():
            download_started.set()
            assert release_download.wait(5)

        voice = MagicMock()
        voice.config.sample_rate = 16000
        with (
            patch("src.tts_engine.scarica_voce_piper", side_effect=slow_download),
            patch.dict("sys.modules", {"piper": self._piper_module(voice)}),
            patch("src.tts_engine.sintetizza_piper", return_value=b"wav"),
            patch("src.tts_engine._wav_to_mp3_bytes", return_value=b"mp3"),
        ):
            first_use = threading.Thread(target=engine.get_preview, args=("Prova.", "paola"))
            first_use.start()
            assert download_started.wait(5)

            loader = threading.Thread(target=engine.load_text, args=("Nuovo testo.", "n.txt"))
            loader.start()
            loader.join(timeout=2)
            loaded_during_download = not loader.is_alive()

            release_download.set()
            first_use.join(5)
            loader.join(5)

        assert loaded_during_download
        assert engine.paragraphs == ["Nuovo testo."]
        assert not first_use.is_alive()

    def test_concurrent_request_never_uses_sample_rate_zero(self, engine):
        config_reached, release_config = threading.Event(), threading.Event()

        class SlowConfigVoice:
            @property
            def config(self):
                config_reached.set()
                assert release_config.wait(5)
                return MagicMock(sample_rate=16000)

        rates = []
        with (
            patch("src.tts_engine.scarica_voce_piper"),
            patch.dict("sys.modules", {"piper": self._piper_module(SlowConfigVoice())}),
            patch(
                "src.tts_engine.sintetizza_piper",
                side_effect=lambda voice, text, rate: rates.append(rate) or b"wav",
            ),
            patch("src.tts_engine._wav_to_mp3_bytes", return_value=b"mp3"),
        ):
            first = threading.Thread(target=engine.get_preview, args=("Uno.", "paola", "neutro"))
            first.start()
            assert config_reached.wait(5)

            second = threading.Thread(target=engine.get_preview, args=("Due.", "paola", "lento"))
            second.start()
            second.join(timeout=1)

            release_config.set()
            first.join(5)
            second.join(5)

        assert not first.is_alive() and not second.is_alive()
        assert rates == [16000, 16000]


class TestEdgeTimeoutCancelsSynthesis:
    """R8: a synthesis abandoned on timeout must not keep running in the async loop."""

    def test_timed_out_edge_synthesis_is_cancelled(self, engine):
        import concurrent.futures

        started, cancelled = threading.Event(), threading.Event()

        async def never_answers(voice_id, text, rate="+0%", pitch="+0Hz"):
            import asyncio

            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return b"too late"

        with (
            patch("src.tts_engine.sintetizza_edge", never_answers),
            pytest.raises(concurrent.futures.TimeoutError),
        ):
            engine._synthesize_text("Ciao", "giuseppe", timeout=0.2)

        assert started.is_set()
        assert cancelled.wait(5)
