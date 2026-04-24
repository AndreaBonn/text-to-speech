"""
tests/test_tts_engine.py
Test per tts_engine.py: cache LRU, sintesi, prefetch, save_all, load_file.

Le dipendenze esterne (edge-tts, piper, ffmpeg) sono sempre mockate.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ===========================================================================
# Fixture
# ===========================================================================


@pytest.fixture()
def engine_con_testo(engine):
    """Engine con 3 paragrafi caricati."""
    engine.load_text(
        "Primo paragrafo.\n\nSecondo paragrafo.\n\nTerzo paragrafo.",
        "test.md",
    )
    return engine


# ===========================================================================
# Test — _concat_mp3_bytes
# ===========================================================================


class TestConcatMp3Bytes:
    """Test per la concatenazione MP3 diretta."""

    def test_concatena_due_mp3(self):
        """Due chunk MP3 devono essere uniti in sequenza."""
        from src.tts_engine import _concat_mp3_bytes

        # Arrange
        chunk1 = b"\xff\xfb\x90\x00" + b"\x00" * 100
        chunk2 = b"\xff\xfb\x90\x00" + b"\x00" * 200

        # Act
        risultato = _concat_mp3_bytes([chunk1, chunk2])

        # Assert
        assert risultato == chunk1 + chunk2
        assert len(risultato) == len(chunk1) + len(chunk2)

    def test_concatena_lista_vuota(self):
        """Una lista vuota deve restituire bytes vuoti."""
        from src.tts_engine import _concat_mp3_bytes

        # Act
        risultato = _concat_mp3_bytes([])

        # Assert
        assert risultato == b""

    def test_concatena_singolo_elemento(self):
        """Un singolo chunk deve essere restituito invariato."""
        from src.tts_engine import _concat_mp3_bytes

        # Arrange
        chunk = b"\xff\xfb\x90\x00data"

        # Act
        risultato = _concat_mp3_bytes([chunk])

        # Assert
        assert risultato == chunk


# ===========================================================================
# Test — TTSEngine.load_file
# ===========================================================================


class TestTTSEngineLoadFile:
    """Test per il caricamento di file Markdown."""

    def test_load_file_chiama_markdown_a_testo(self, engine, tmp_path):
        """load_file deve usare markdown_a_testo per la conversione."""
        # Arrange
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Titolo\n\nParagrafo uno.\n\nParagrafo due.")

        with patch(
            "src.tts_engine.file_a_testo",
            return_value="Paragrafo uno.\n\nParagrafo due.",
        ) as mock_conv:
            # Act
            paragrafi = engine.load_file(md_file)

        # Assert
        mock_conv.assert_called_once_with(md_file)
        assert len(paragrafi) == 2
        assert paragrafi[0] == "Paragrafo uno."
        assert paragrafi[1] == "Paragrafo due."
        assert engine.filename == "doc.md"

    def test_load_file_pulisce_cache_precedente(self, engine):
        """Caricare un nuovo file deve svuotare la cache."""
        # Arrange — carica primo testo e popola cache manualmente
        engine.load_text("Vecchio testo.", "old.md")
        engine._put_cache("giuseppe:neutro:0", b"fake_mp3")
        assert len(engine._cache) == 1

        # Act — carica nuovo testo
        with patch(
            "src.tts_engine.file_a_testo",
            return_value="Nuovo testo.",
        ):
            engine.load_file(Path("/fake/new.md"))

        # Assert
        assert len(engine._cache) == 0
        assert engine.filename == "new.md"

    def test_load_file_ignora_paragrafi_vuoti(self, engine):
        """Paragrafi vuoti (solo whitespace) devono essere esclusi."""
        # Arrange
        with patch(
            "src.tts_engine.file_a_testo",
            return_value="Testo.\n\n   \n\n\n\nAltro testo.",
        ):
            # Act
            paragrafi = engine.load_file(Path("/fake/test.md"))

        # Assert
        assert len(paragrafi) == 2
        assert paragrafi[0] == "Testo."
        assert paragrafi[1] == "Altro testo."


# ===========================================================================
# Test — TTSEngine cache LRU
# ===========================================================================


class TestTTSEngineCache:
    """Test per la cache LRU con eviction."""

    def test_cache_eviction_al_superamento_max(self, engine):
        """La cache deve evictare gli elementi più vecchi oltre MAX_CACHE."""
        from src.tts_engine import MAX_CACHE

        # Arrange — inserisci MAX_CACHE + 5 elementi
        for i in range(MAX_CACHE + 5):
            engine._put_cache(f"voice:{i}", f"data_{i}".encode())

        # Assert — la cache non deve superare MAX_CACHE
        assert len(engine._cache) == MAX_CACHE

        # I primi 5 elementi devono essere stati evictati
        assert "voice:0" not in engine._cache
        assert "voice:4" not in engine._cache

        # L'ultimo elemento deve essere presente
        assert f"voice:{MAX_CACHE + 4}" in engine._cache

    def test_cache_move_to_end_su_accesso(self, engine_con_testo):
        """Accedere a un elemento in cache deve spostarlo in fondo (MRU)."""
        # Arrange — popola cache con 3 elementi
        engine_con_testo._put_cache("giuseppe:neutro:0", b"mp3_0")
        engine_con_testo._put_cache("giuseppe:neutro:1", b"mp3_1")
        engine_con_testo._put_cache("giuseppe:neutro:2", b"mp3_2")

        # Act — accedi al primo elemento (dovrebbe spostarlo in fondo)
        with patch.object(engine_con_testo, "_synthesize", return_value=b"mp3_0"):
            engine_con_testo.get_audio(0, "giuseppe")

        # Assert — "giuseppe:neutro:0" deve essere l'ultimo (MRU)
        keys = list(engine_con_testo._cache.keys())
        assert keys[-1] == "giuseppe:neutro:0"

    def test_clear_cache_svuota_completamente(self, engine):
        """_clear_cache deve rimuovere tutti gli elementi."""
        # Arrange
        engine._put_cache("a", b"1")
        engine._put_cache("b", b"2")
        assert len(engine._cache) == 2

        # Act
        engine._clear_cache()

        # Assert
        assert len(engine._cache) == 0


# ===========================================================================
# Test — TTSEngine._synthesize
# ===========================================================================


class TestTTSEngineSynthesize:
    """Test per il dispatch di sintesi verso Edge o Piper."""

    def test_synthesize_edge_usa_async_loop(self, engine_con_testo):
        """Per voci Edge, deve usare run_coroutine_threadsafe con _async_loop."""
        # Arrange
        fake_mp3 = b"ID3\x00edge_audio"

        with patch("src.tts_engine.asyncio.run_coroutine_threadsafe") as mock_rcs:
            mock_future = MagicMock()
            mock_future.result.return_value = fake_mp3
            mock_rcs.return_value = mock_future

            # Act
            risultato = engine_con_testo._synthesize(0, "giuseppe")

        # Assert
        mock_rcs.assert_called_once()
        # Verifica che usi il loop dedicato _async_loop
        from src.tts_engine import _async_loop

        assert mock_rcs.call_args[0][1] is _async_loop
        mock_future.result.assert_called_once_with(timeout=60)
        assert risultato == fake_mp3

    def test_synthesize_piper_carica_modello_lazy(self, engine_con_testo):
        """Per voci Piper, deve caricare il modello al primo uso."""
        # Arrange
        fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
        fake_mp3 = b"ID3\x00piper_audio"

        with (
            patch.object(engine_con_testo, "_load_piper") as mock_load,
            patch("src.tts_engine.sintetizza_piper", return_value=fake_wav),
            patch("src.tts_engine._wav_to_mp3_bytes", return_value=fake_mp3),
        ):
            # Act
            risultato = engine_con_testo._synthesize(0, "paola")

        # Assert
        mock_load.assert_called_once()
        assert risultato == fake_mp3

    def test_synthesize_piper_non_ricarica_modello(self, engine_con_testo):
        """Se il modello Piper è già caricato, non deve ricaricarlo."""
        # Arrange — simula modello già caricato
        engine_con_testo._piper_voice = MagicMock()
        engine_con_testo._piper_sample_rate = 22050
        fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
        fake_mp3 = b"ID3\x00piper_audio"

        with (
            patch("src.tts_engine.sintetizza_piper", return_value=fake_wav),
            patch("src.tts_engine._wav_to_mp3_bytes", return_value=fake_mp3),
            patch.object(engine_con_testo, "_load_piper") as mock_load,
        ):
            # Act
            engine_con_testo._synthesize(0, "paola")

        # Assert — _load_piper NON deve essere chiamato
        mock_load.assert_not_called()


# ===========================================================================
# Test — TTSEngine.save_all
# ===========================================================================


class TestTTSEngineSaveAll:
    """Test per la generazione del file MP3 completo."""

    def test_save_all_concatena_tutti_i_paragrafi(self, engine_con_testo):
        """save_all deve sintetizzare e concatenare tutti i paragrafi."""
        # Arrange
        mp3_chunks = [b"chunk_0", b"chunk_1", b"chunk_2"]

        with patch.object(
            engine_con_testo,
            "_synthesize",
            side_effect=lambda i, v, s: mp3_chunks[i],
        ):
            # Act
            risultato = engine_con_testo.save_all("giuseppe")

        # Assert — i bytes devono essere la concatenazione in ordine
        assert risultato == b"chunk_0" + b"chunk_1" + b"chunk_2"

    def test_save_all_usa_cache_se_disponibile(self, engine_con_testo):
        """save_all deve usare la cache per i paragrafi già sintetizzati."""
        # Arrange — pre-popola cache per paragrafo 0
        engine_con_testo._put_cache("giuseppe:neutro:0", b"cached_0")
        call_count = 0

        def fake_synthesize(i, v, s):
            nonlocal call_count
            call_count += 1
            return f"synth_{i}".encode()

        with patch.object(engine_con_testo, "_synthesize", side_effect=fake_synthesize):
            # Act
            risultato = engine_con_testo.save_all("giuseppe")

        # Assert — _synthesize chiamato solo per paragrafi 1 e 2 (non 0)
        assert call_count == 2
        assert risultato == b"cached_0synth_1synth_2"

    def test_save_all_senza_paragrafi_restituisce_vuoto(self, engine):
        """save_all senza paragrafi caricati deve restituire bytes vuoti."""
        # Act
        risultato = engine.save_all("giuseppe")

        # Assert
        assert risultato == b""


# ===========================================================================
# Test — TTSEngine.prefetch
# ===========================================================================


class TestTTSEnginePrefetch:
    """Test per il prefetch in background."""

    def test_prefetch_non_blocca(self, engine_con_testo):
        """prefetch deve ritornare immediatamente (non bloccante)."""
        # Arrange
        with patch.object(engine_con_testo, "_synthesize", return_value=b"mp3"):
            # Act & Assert — deve completare in meno di 1 secondo
            start = time.monotonic()
            engine_con_testo.prefetch(0, "giuseppe")
            elapsed = time.monotonic() - start

            assert elapsed < 1.0

    def test_prefetch_skip_se_gia_in_cache(self, engine_con_testo):
        """Se il paragrafo è già in cache, il prefetch non deve fare nulla."""
        # Arrange
        engine_con_testo._put_cache("giuseppe:neutro:0", b"cached")

        with patch.object(engine_con_testo, "_synthesize") as mock_synth:
            # Act
            engine_con_testo.prefetch(0, "giuseppe")
            # Attendi brevemente per il thread pool
            time.sleep(0.1)

        # Assert — _synthesize NON deve essere chiamato
        mock_synth.assert_not_called()

    def test_prefetch_ignora_indice_fuori_range(self, engine_con_testo):
        """Indici fuori range devono essere ignorati silenziosamente."""
        # Act & Assert — non deve lanciare eccezioni
        engine_con_testo.prefetch(-1, "giuseppe")
        engine_con_testo.prefetch(999, "giuseppe")

    def test_prefetch_inserisce_in_cache(self, engine_con_testo):
        """Il prefetch deve inserire il risultato in cache al completamento."""
        # Arrange
        fake_mp3 = b"prefetched_mp3"

        with (
            patch.object(engine_con_testo, "_synthesize", return_value=fake_mp3),
            patch("src.tts_engine._executor") as mock_exec,
        ):
            # Esegui il task sincrono (elimina race condition da CI)
            mock_exec.submit.side_effect = lambda fn: fn()
            # Act
            engine_con_testo.prefetch(0, "giuseppe")

        # Assert
        assert "giuseppe:neutro:0" in engine_con_testo._cache
        assert engine_con_testo._cache["giuseppe:neutro:0"] == fake_mp3


# ===========================================================================
# Test — TTSEngine.get_audio (integrazioni con cache e prefetch)
# ===========================================================================


class TestTTSEngineGetAudioIntegration:
    """Test di integrazione per get_audio con cache e prefetch."""

    def test_get_audio_lancia_prefetch_per_prossimo(self, engine_con_testo):
        """get_audio deve lanciare il prefetch del paragrafo successivo."""
        # Arrange
        with (
            patch.object(engine_con_testo, "_synthesize", return_value=b"mp3"),
            patch.object(engine_con_testo, "prefetch") as mock_prefetch,
        ):
            # Act
            engine_con_testo.get_audio(0, "giuseppe")

        # Assert — prefetch chiamato per il paragrafo 1
        mock_prefetch.assert_called_once_with(1, "giuseppe", "neutro")

    def test_get_audio_no_prefetch_su_ultimo_paragrafo(self, engine_con_testo):
        """L'ultimo paragrafo non deve triggerare il prefetch."""
        # Arrange
        ultimo_idx = len(engine_con_testo.paragraphs) - 1

        with (
            patch.object(engine_con_testo, "_synthesize", return_value=b"mp3"),
            patch.object(engine_con_testo, "prefetch") as mock_prefetch,
        ):
            # Act
            engine_con_testo.get_audio(ultimo_idx, "giuseppe")

        # Assert — prefetch NON chiamato
        mock_prefetch.assert_not_called()

    def test_get_audio_voci_diverse_non_condividono_cache(self, engine_con_testo):
        """Voci diverse devono avere entry di cache separate."""

        # Arrange
        def fake_synth(idx, voice, style):
            return f"mp3_{voice}".encode()

        with patch.object(engine_con_testo, "_synthesize", side_effect=fake_synth):
            # Act
            audio_g = engine_con_testo.get_audio(0, "giuseppe")
            audio_i = engine_con_testo.get_audio(0, "isabella")

        # Assert
        assert audio_g != audio_i
        assert "giuseppe:neutro:0" in engine_con_testo._cache
        assert "isabella:neutro:0" in engine_con_testo._cache


# ===========================================================================
# Test — TTSEngine._load_piper (idempotenza)
# ===========================================================================


class TestTTSEngineLoadPiper:
    """Test per il caricamento lazy del modello Piper."""

    def test_load_piper_idempotente(self, engine):
        """Chiamare _load_piper due volte deve caricare il modello una sola volta."""
        # Arrange
        mock_voice = MagicMock()
        mock_voice.config.sample_rate = 22050
        mock_piper_module = MagicMock()
        mock_piper_module.PiperVoice.load.return_value = mock_voice

        # PiperVoice viene importato lazy dentro _load_piper con
        # "from piper import PiperVoice", quindi patchiamo il modulo piper
        with (
            patch("src.tts_engine.scarica_voce_piper"),
            patch.dict("sys.modules", {"piper": mock_piper_module}),
        ):
            # Act — chiama due volte
            engine._load_piper()
            engine._load_piper()

        # Assert — PiperVoice.load chiamato una sola volta
        mock_piper_module.PiperVoice.load.assert_called_once()
        assert engine._piper_voice is mock_voice
        assert engine._piper_sample_rate == 22050


# ===========================================================================
# Test — _wav_to_mp3_bytes
# ===========================================================================


class TestWavToMp3Bytes:
    """Test per la conversione WAV→MP3 tramite ffmpeg."""

    def test_chiama_ffmpeg_con_pipe(self):
        """Deve invocare ffmpeg con input/output su pipe e codec lame."""
        from src.tts_engine import _wav_to_mp3_bytes

        # Arrange
        fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
        fake_mp3 = b"ID3\x00fake_mp3"
        mock_result = MagicMock()
        mock_result.stdout = fake_mp3

        with patch("src.tts_engine.subprocess.run", return_value=mock_result) as mock_run:
            # Act
            _wav_to_mp3_bytes(fake_wav)

        # Assert — verifica argomenti chiave del comando ffmpeg
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert cmd[0] == "ffmpeg"
        assert "pipe:0" in cmd
        assert "libmp3lame" in cmd
        assert "pipe:1" in cmd
        assert kwargs["input"] == fake_wav
        assert kwargs["check"] is True

    def test_restituisce_stdout_di_ffmpeg(self):
        """Il valore di ritorno deve corrispondere a result.stdout."""
        from src.tts_engine import _wav_to_mp3_bytes

        # Arrange
        fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
        fake_mp3 = b"ID3\x00fake_mp3_output"
        mock_result = MagicMock()
        mock_result.stdout = fake_mp3

        with patch("src.tts_engine.subprocess.run", return_value=mock_result):
            # Act
            risultato = _wav_to_mp3_bytes(fake_wav)

        # Assert
        assert risultato == fake_mp3

    def test_propaga_errore_ffmpeg(self):
        """Se ffmpeg fallisce, CalledProcessError deve propagarsi al chiamante."""
        import subprocess as stdlib_subprocess

        from src.tts_engine import _wav_to_mp3_bytes

        # Arrange
        fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
        errore = stdlib_subprocess.CalledProcessError(returncode=1, cmd=["ffmpeg"], stderr=b"error")

        with (
            patch("src.tts_engine.subprocess.run", side_effect=errore),
            pytest.raises(stdlib_subprocess.CalledProcessError),
        ):
            # Act
            _wav_to_mp3_bytes(fake_wav)


# ===========================================================================
# Test — TTSEngine._synthesize (race condition)
# ===========================================================================


class TestSynthesizeRaceCondition:
    """Test per il path di IndexError durante la sintesi (race condition)."""

    def test_synthesize_index_fuori_range_durante_sintesi(self, engine):
        """Se i paragrafi vengono azzerati tra il check in get_audio e l'acquisizione
        del lock in _synthesize, deve essere sollevato IndexError."""
        # Arrange — carica un paragrafo, poi simula la race condition svuotando la lista
        engine.load_text("Solo un paragrafo.", "test.md")
        engine._paragraphs = []  # race: azzerato prima che _synthesize acquisisca il lock

        # Act & Assert
        with pytest.raises(IndexError, match="fuori range"):
            engine._synthesize(0, "giuseppe")
