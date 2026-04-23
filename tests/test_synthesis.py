"""
tests/test_synthesis.py
Test per le funzioni di sintesi vocale: Piper TTS e Edge TTS.
"""

import asyncio
import io
import wave
from unittest.mock import MagicMock, patch

import pytest

from src.synthesis import scarica_voce_piper, sintetizza_piper

# ===========================================================================
# Test — sintetizza_piper
# ===========================================================================


class TestSintetizzaPiper:
    """Test per la sintesi WAV con Piper."""

    def test_restituisce_wav_valido(self):
        """Il risultato deve essere un WAV mono 16-bit con il sample rate dato."""
        mock_voce = MagicMock()
        sample_rate = 22050

        risultato = sintetizza_piper(mock_voce, "Ciao mondo", sample_rate)

        assert isinstance(risultato, bytes)
        with wave.open(io.BytesIO(risultato), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == sample_rate

    def test_chiama_synthesize_wav_con_testo(self):
        """Deve passare il testo e il wave writer a PiperVoice."""
        mock_voce = MagicMock()
        testo = "Paragrafo di prova"

        sintetizza_piper(mock_voce, testo, 16000)

        mock_voce.synthesize_wav.assert_called_once()
        args = mock_voce.synthesize_wav.call_args
        assert args[0][0] == testo

    def test_sample_rate_diversi(self):
        """Deve rispettare il sample rate fornito."""
        mock_voce = MagicMock()

        for sr in [16000, 22050, 44100]:
            risultato = sintetizza_piper(mock_voce, "Test", sr)
            with wave.open(io.BytesIO(risultato), "rb") as wf:
                assert wf.getframerate() == sr


# ===========================================================================
# Test — sintetizza_edge
# ===========================================================================


def _run_async(coro):
    """Helper per eseguire coroutine senza pytest-asyncio."""
    return asyncio.run(coro)


class TestSintetizzaEdge:
    """Test per la sintesi MP3 con Edge TTS."""

    def _make_mock_edge(self, chunks):
        """Crea mock edge_tts module con stream che restituisce i chunk dati."""
        mock_edge = MagicMock()
        mock_comm = MagicMock()

        async def mock_stream():
            for c in chunks:
                yield c

        mock_comm.stream = mock_stream
        mock_edge.Communicate.return_value = mock_comm
        return mock_edge

    def test_restituisce_bytes_audio(self):
        """Deve restituire bytes MP3 concatenati dai chunk audio."""
        from src.synthesis import sintetizza_edge

        chunks = [
            {"type": "audio", "data": b"\xff\xfb\x90\x00"},
            {"type": "metadata", "data": b"info"},
            {"type": "audio", "data": b"\xff\xfb\x90\x01"},
        ]
        mock_edge = self._make_mock_edge(chunks)

        with patch.dict("sys.modules", {"edge_tts": mock_edge}):
            risultato = _run_async(sintetizza_edge("it-IT-GiuseppeNeural", "Ciao"))

        assert risultato == b"\xff\xfb\x90\x00\xff\xfb\x90\x01"

    def test_parametri_rate_e_pitch(self):
        """Deve passare rate e pitch a edge_tts.Communicate."""
        from src.synthesis import sintetizza_edge

        mock_edge = self._make_mock_edge([])

        async def empty_stream():
            return
            yield

        mock_edge.Communicate.return_value.stream = empty_stream

        with patch.dict("sys.modules", {"edge_tts": mock_edge}):
            _run_async(sintetizza_edge("it-IT-GiuseppeNeural", "Test", rate="+13%", pitch="-3Hz"))

        mock_edge.Communicate.assert_called_once_with(
            "Test", "it-IT-GiuseppeNeural", rate="+13%", pitch="-3Hz"
        )

    def test_nessun_chunk_audio_restituisce_vuoto(self):
        """Se lo stream non contiene chunk audio, restituisce bytes vuoti."""
        from src.synthesis import sintetizza_edge

        mock_edge = self._make_mock_edge(
            [
                {"type": "metadata", "data": b"info"},
            ]
        )

        with patch.dict("sys.modules", {"edge_tts": mock_edge}):
            risultato = _run_async(sintetizza_edge("it-IT-IsabellaNeural", "Vuoto"))

        assert risultato == b""


# ===========================================================================
# Test — scarica_voce_piper (download e errore)
# ===========================================================================


class TestScaricaVocePiperDownload:
    """Test per il download effettivo e la gestione errori."""

    def test_download_effettivo_scrive_file(self):
        """Deve scaricare e scrivere il file se non esiste."""
        mock_dest = MagicMock()
        mock_dest.exists.return_value = False
        mock_dest.name = "model.onnx"

        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "128"}
        mock_response.read.side_effect = [b"x" * 64, b"y" * 64, b""]
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)

        with (
            patch("src.synthesis.VOICE_DIR"),
            patch(
                "src.synthesis.VOICE_URLS",
                {mock_dest: "http://example.com/model.onnx"},
            ),
            patch("src.synthesis.urllib.request.urlopen", return_value=mock_response),
            patch("builtins.open", return_value=mock_file),
            patch("builtins.print"),
        ):
            scarica_voce_piper()

        assert mock_file.write.call_count == 2

    def test_download_fallito_solleva_runtime_error(self):
        """Deve sollevare RuntimeError se il download fallisce."""
        mock_dest = MagicMock()
        mock_dest.exists.return_value = False
        mock_dest.name = "model.onnx"

        with (
            patch("src.synthesis.VOICE_DIR"),
            patch(
                "src.synthesis.VOICE_URLS",
                {mock_dest: "http://example.com/model.onnx"},
            ),
            patch(
                "src.synthesis.urllib.request.urlopen",
                side_effect=ConnectionError("Network down"),
            ),
            pytest.raises(RuntimeError, match="Download voce Piper fallito"),
        ):
            scarica_voce_piper()

    def test_download_senza_content_length(self):
        """Deve funzionare anche senza header Content-Length (no progress bar)."""
        mock_dest = MagicMock()
        mock_dest.exists.return_value = False
        mock_dest.name = "model.onnx"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.read.side_effect = [b"data", b""]
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)

        with (
            patch("src.synthesis.VOICE_DIR"),
            patch(
                "src.synthesis.VOICE_URLS",
                {mock_dest: "http://example.com/model.onnx"},
            ),
            patch("src.synthesis.urllib.request.urlopen", return_value=mock_response),
            patch("builtins.open", return_value=mock_file),
            patch("builtins.print"),
        ):
            scarica_voce_piper()

        mock_file.write.assert_called_once_with(b"data")
