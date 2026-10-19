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

    def test_il_wav_contiene_i_frame_scritti_dalla_voce(self):
        """I frame che la voce scrive nel writer ricevuto finiscono nel WAV restituito."""
        frames = b"\x01\x00\x02\x00\x03\x00" * 50  # 150 campioni a 16 bit
        scritto_su = []

        class VoceFinta:
            def synthesize_wav(self, testo, wav_file):
                scritto_su.append(wav_file)
                wav_file.writeframes(frames)

        risultato = sintetizza_piper(VoceFinta(), "Ciao", 22050)

        with wave.open(io.BytesIO(risultato), "rb") as wf:
            assert wf.getnframes() == 150
            assert wf.readframes(150) == frames
        assert isinstance(scritto_su[0], wave.Wave_write)

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

        mock_edge = self._make_mock_edge([{"type": "audio", "data": b"mp3"}])

        with patch.dict("sys.modules", {"edge_tts": mock_edge}):
            _run_async(sintetizza_edge("it-IT-GiuseppeNeural", "Test", rate="+13%", pitch="-3Hz"))

        mock_edge.Communicate.assert_called_once_with(
            "Test", "it-IT-GiuseppeNeural", rate="+13%", pitch="-3Hz"
        )

    def test_nessun_chunk_audio_solleva_errore(self):
        """Uno stream senza audio è un guasto di Edge, non un MP3 valido."""
        from src.synthesis import sintetizza_edge

        mock_edge = self._make_mock_edge(
            [
                {"type": "metadata", "data": b"info"},
            ]
        )

        with (
            patch.dict("sys.modules", {"edge_tts": mock_edge}),
            pytest.raises(RuntimeError, match="no audio"),
        ):
            _run_async(sintetizza_edge("it-IT-IsabellaNeural", "Vuoto"))


# ===========================================================================
# Test — scarica_voce_piper (download e errore)
# ===========================================================================


class TestScaricaVocePiperDownload:
    """Download del modello: file finale solo a download completo, mai troncato."""

    URL = "http://example.com/model.onnx"

    @staticmethod
    def _urlopen(chunks, content_length=None):
        """Fake urlopen: stream dei chunk dati; un'eccezione nella lista viene sollevata."""
        risposta = MagicMock()
        risposta.headers = {} if content_length is None else {"Content-Length": str(content_length)}
        risposta.read.side_effect = [*chunks, b""]
        fake = MagicMock()
        fake.return_value.__enter__.return_value = risposta
        return fake

    def _scarica(self, tmp_path, fake_urlopen):
        dest = tmp_path / "model.onnx"
        with (
            patch("src.synthesis.VOICE_DIR", tmp_path),
            patch("src.synthesis.VOICE_URLS", {dest: self.URL}),
            patch("src.synthesis.urllib.request.urlopen", fake_urlopen),
            patch("builtins.print"),
        ):
            scarica_voce_piper()
        return dest

    def test_download_completo_scrive_il_file(self, tmp_path):
        fake = self._urlopen([b"x" * 64, b"y" * 64], content_length=128)

        dest = self._scarica(tmp_path, fake)

        assert dest.read_bytes() == b"x" * 64 + b"y" * 64
        assert sorted(p.name for p in tmp_path.iterdir()) == ["model.onnx"]

    def test_download_usa_un_timeout(self, tmp_path):
        fake = self._urlopen([b"dati"])

        self._scarica(tmp_path, fake)

        fake.assert_called_once_with(self.URL, timeout=30)

    def test_download_senza_content_length(self, tmp_path):
        dest = self._scarica(tmp_path, self._urlopen([b"data"]))

        assert dest.read_bytes() == b"data"

    def test_connessione_rifiutata_solleva_runtime_error(self, tmp_path):
        fake = MagicMock(side_effect=ConnectionError("Network down"))

        with pytest.raises(RuntimeError, match="Download voce Piper fallito"):
            self._scarica(tmp_path, fake)

        assert list(tmp_path.iterdir()) == []

    def test_interruzione_a_meta_non_lascia_file(self, tmp_path):
        fake = self._urlopen([b"x" * 64, OSError("connection reset")], content_length=128)

        with pytest.raises(RuntimeError, match="connection reset"):
            self._scarica(tmp_path, fake)

        assert list(tmp_path.iterdir()) == []

    def test_download_piu_corto_del_content_length_e_un_errore(self, tmp_path):
        fake = self._urlopen([b"x" * 64], content_length=128)

        with pytest.raises(RuntimeError, match="64 di 128"):
            self._scarica(tmp_path, fake)

        assert list(tmp_path.iterdir()) == []

    def test_risposta_vuota_senza_content_length_e_un_errore(self, tmp_path):
        with pytest.raises(RuntimeError, match="vuoto"):
            self._scarica(tmp_path, self._urlopen([]))

        assert list(tmp_path.iterdir()) == []

    def test_non_tocca_il_file_parziale_di_un_altro_download(self, tmp_path):
        """Web e CLI possono scaricare insieme: ognuno usa il proprio file temporaneo."""
        altrui = tmp_path / "model.onnx.part"
        altrui.write_bytes(b"download in corso di un altro processo")

        dest = self._scarica(tmp_path, self._urlopen([b"dati"]))

        assert dest.read_bytes() == b"dati"
        assert altrui.read_bytes() == b"download in corso di un altro processo"
