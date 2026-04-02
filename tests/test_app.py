"""
tests/test_app.py
Test suite per TTS Reader: leggi, app (Flask), tts_engine.

Dipendenze esterne (edge-tts, piper, ffmpeg) sono sempre mockata
per garantire test isolati e veloci.
"""

import io
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ===========================================================================
# Test — leggi.py
# ===========================================================================


class TestMarkdownATesto:
    """Test per il convertitore Markdown (fallback regex, senza pandoc)."""

    def _converti(self, markdown: str) -> str:
        """Helper: converte Markdown via file temp con fallback regex forzato."""
        from converters import file_a_testo

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(markdown)
            tmp_path = Path(f.name)

        try:
            with patch("converters.shutil.which", return_value=None):
                return file_a_testo(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_markdown_a_testo_headers(self):
        """I titoli markdown (# ## ###) devono essere rimossi dal testo."""
        # Arrange
        markdown = "# Titolo principale\n\n## Sottotitolo\n\n### Terzo livello"

        # Act
        risultato = self._converti(markdown)

        # Assert
        assert "#" not in risultato
        assert "Titolo principale" in risultato
        assert "Sottotitolo" in risultato
        assert "Terzo livello" in risultato

    def test_markdown_a_testo_bold_italic(self):
        """Bold (**testo**) e italic (*testo*) devono essere eliminati."""
        # Arrange
        markdown = "Questo è **grassetto** e questo è *corsivo*."

        # Act
        risultato = self._converti(markdown)

        # Assert
        assert "**" not in risultato
        assert "*" not in risultato
        assert "grassetto" in risultato
        assert "corsivo" in risultato

    def test_markdown_a_testo_links(self):
        """I link [testo](url) devono diventare solo il testo visibile."""
        # Arrange
        markdown = "Visita [OpenAI](https://openai.com) per saperne di più."

        # Act
        risultato = self._converti(markdown)

        # Assert
        assert "https://openai.com" not in risultato
        assert "[" not in risultato
        assert "]" not in risultato
        assert "OpenAI" in risultato

    def test_markdown_a_testo_code_blocks(self):
        """I blocchi di codice inline e multiriga devono essere rimossi."""
        # Arrange
        markdown = (
            "Usa il comando `pip install flask` per installare.\n\n"
            "```python\ndef hello():\n    return 'world'\n```"
        )

        # Act
        risultato = self._converti(markdown)

        # Assert
        assert "```" not in risultato
        assert "`" not in risultato
        # Il testo attorno ai code block rimane
        assert "Usa il comando" in risultato

    def test_markdown_a_testo_empty(self):
        """Un file vuoto deve restituire una stringa vuota."""
        # Arrange
        markdown = ""

        # Act
        risultato = self._converti(markdown)

        # Assert
        assert risultato == ""


# ===========================================================================
# Test — app.py (Flask test client)
# ===========================================================================


class TestIndexEndpoint:
    def test_index_returns_html(self, client):
        """GET / deve restituire 200 con Content-Type text/html."""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200
        assert b"html" in response.data.lower()


class TestVoicesEndpoint:
    def test_voices_endpoint(self, client):
        """GET /api/voices deve restituire le 5 voci con struttura corretta."""
        # Act
        response = client.get("/api/voices")
        data = response.get_json()

        # Assert
        assert response.status_code == 200
        assert "voices" in data
        assert "default" in data
        assert len(data["voices"]) == 5

        # Ogni voce deve avere i campi obbligatori
        campi_obbligatori = {"id", "label", "type", "multilingual", "gender"}
        for voce in data["voices"]:
            assert campi_obbligatori <= voce.keys(), (
                f"Voce {voce.get('id')} mancante di campi: {campi_obbligatori - voce.keys()}"
            )

        # Verifica che la voce di default esista nella lista
        ids_disponibili = {v["id"] for v in data["voices"]}
        assert data["default"] in ids_disponibili


class TestLoadEndpoint:
    def test_load_no_file(self, client):
        """POST /api/load senza file deve restituire 400."""
        # Act
        response = client.post("/api/load", data={})

        # Assert
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_load_unsupported_format(self, client):
        """POST /api/load con formato non supportato deve restituire 400."""
        # Arrange
        file_csv = (io.BytesIO(b"a,b,c"), "dati.csv")

        # Act
        response = client.post(
            "/api/load",
            data={"file": file_csv},
            content_type="multipart/form-data",
        )

        # Assert
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_load_valid_file(self, client):
        """POST /api/load con file .md valido deve restituire i paragrafi."""
        # Arrange
        contenuto_md = b"# Titolo\n\nPrimo paragrafo del documento.\n\nSecondo paragrafo."
        file_md = (io.BytesIO(contenuto_md), "test.md")

        mock_paragraphs = ["Primo paragrafo del documento.", "Secondo paragrafo."]

        # Act — mock engine.load_file per evitare pandoc/filesystem reali
        with patch("app.engine.load_file", return_value=mock_paragraphs):
            response = client.post(
                "/api/load",
                data={"file": file_md},
                content_type="multipart/form-data",
            )

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert "filename" in data
        assert "total" in data
        assert "paragraphs" in data
        assert data["total"] == len(mock_paragraphs)
        assert data["filename"] == "test.md"

        # Ogni paragrafo deve avere idx, text, chars
        for par in data["paragraphs"]:
            assert "idx" in par
            assert "text" in par
            assert "chars" in par
            assert par["chars"] == len(par["text"])


class TestAudioEndpoint:
    def test_audio_no_file_loaded(self, client):
        """GET /api/audio/0 senza file caricato deve restituire 400."""
        # Arrange — engine senza paragrafi (resettato dal fixture)

        # Act
        response = client.get("/api/audio/0")

        # Assert
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_audio_invalid_voice(self, client):
        """GET /api/audio/0?voice=nonexistent deve restituire 400."""
        # Arrange — voice inesistente

        # Act
        response = client.get("/api/audio/0?voice=nonexistent")

        # Assert
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data


class TestSaveEndpoint:
    def test_save_no_file_loaded(self, client):
        """POST /api/save senza file caricato deve restituire 400."""
        # Arrange — engine senza paragrafi (resettato dal fixture)

        # Act
        response = client.post(
            "/api/save",
            data='{"voice": "giuseppe"}',
            content_type="application/json",
        )

        # Assert
        assert response.status_code == 400
        assert "error" in response.get_json()


# ===========================================================================
# Test — tts_engine.py
# ===========================================================================


class TestTTSEngine:
    def test_engine_paragraphs_empty(self, engine):
        """Un engine appena creato deve avere la lista paragrafi vuota."""
        # Assert
        assert engine.paragraphs == []
        assert engine.filename == ""

    def test_engine_load_text(self, engine):
        """load_text deve splittare il testo per paragrafi doppi newline."""
        # Arrange
        testo = "Primo paragrafo.\n\nSecondo paragrafo.\n\nTerzo paragrafo."
        filename = "documento.md"

        # Act
        paragrafi = engine.load_text(testo, filename)

        # Assert
        assert len(paragrafi) == 3
        assert paragrafi[0] == "Primo paragrafo."
        assert paragrafi[1] == "Secondo paragrafo."
        assert paragrafi[2] == "Terzo paragrafo."
        assert engine.filename == filename
        assert engine.paragraphs == paragrafi

    def test_engine_load_text_strips_whitespace(self, engine):
        """load_text deve eliminare paragrafi vuoti e spazi iniziali/finali."""
        # Arrange
        testo = "\n\n  Paragrafo con spazi  \n\n\n\nAltro paragrafo.\n\n"

        # Act
        paragrafi = engine.load_text(testo, "test.md")

        # Assert — solo paragrafi non vuoti dopo strip
        assert len(paragrafi) == 2
        assert paragrafi[0] == "Paragrafo con spazi"
        assert paragrafi[1] == "Altro paragrafo."

    def test_engine_cache_hit(self, engine):
        """get_audio deve usare la cache e non chiamare _synthesize due volte."""
        # Arrange
        engine.load_text("Paragrafo di test.", "test.md")
        fake_mp3 = b"ID3\x00fake_mp3_content"

        with patch.object(engine, "_synthesize", return_value=fake_mp3) as mock_synth:
            # Act — prima chiamata: sintesi + inserimento cache
            risultato_1 = engine.get_audio(0, "giuseppe")

            # Resetto il mock per verificare che la seconda chiamata NON chiami _synthesize
            mock_synth.reset_mock()

            # Act — seconda chiamata: deve usare la cache
            risultato_2 = engine.get_audio(0, "giuseppe")

        # Assert
        assert risultato_1 == fake_mp3
        assert risultato_2 == fake_mp3
        # La seconda chiamata NON deve aver invocato _synthesize
        mock_synth.assert_not_called()

    def test_engine_index_out_of_range(self, engine):
        """get_audio con indice invalido deve sollevare IndexError."""
        # Arrange
        engine.load_text("Un solo paragrafo.", "test.md")

        # Act & Assert — indice troppo alto
        with pytest.raises(IndexError):
            engine.get_audio(99, "giuseppe")

    def test_engine_index_negative(self, engine):
        """get_audio con indice negativo deve sollevare IndexError."""
        # Arrange
        engine.load_text("Paragrafo.", "test.md")

        # Act & Assert
        with pytest.raises(IndexError):
            engine.get_audio(-1, "giuseppe")

    def test_engine_cache_different_voices(self, engine):
        """Cache key include la voce: voci diverse non condividono cache."""
        # Arrange
        engine.load_text("Paragrafo test.", "test.md")
        mp3_giuseppe = b"mp3_giuseppe"
        mp3_isabella = b"mp3_isabella"

        def fake_synthesize(index, voice, style):
            return mp3_giuseppe if voice == "giuseppe" else mp3_isabella

        with patch.object(engine, "_synthesize", side_effect=fake_synthesize):
            # Act
            audio_giuseppe = engine.get_audio(0, "giuseppe")
            audio_isabella = engine.get_audio(0, "isabella")

        # Assert — risultati distinti per voce diversa
        assert audio_giuseppe == mp3_giuseppe
        assert audio_isabella == mp3_isabella
        assert audio_giuseppe != audio_isabella


# ===========================================================================
# Test — TTSEngine._synthesize
# ===========================================================================


class TestSynthesize:
    def test_synthesize_edge_uses_async_loop(self, engine):
        """_synthesize con voce Edge deve usare run_coroutine_threadsafe."""
        # Arrange
        engine.load_text("Testo di test.", "test.md")
        fake_mp3 = b"ID3\x00fake_edge_mp3"

        with patch("tts_engine.asyncio.run_coroutine_threadsafe") as mock_rcs:
            mock_future = MagicMock()
            mock_future.result.return_value = fake_mp3
            mock_rcs.return_value = mock_future

            # Act
            result = engine._synthesize(0, "giuseppe")

        # Assert
        assert result == fake_mp3
        mock_rcs.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=60)

    def test_synthesize_piper_loads_model_lazy(self, engine):
        """_synthesize con voce Piper deve caricare il modello e convertire WAV in MP3."""
        # Arrange
        engine.load_text("Testo Piper.", "test.md")
        fake_wav = b"RIFF\x00\x00fake_wav"
        fake_mp3 = b"ID3\x00fake_piper_mp3"

        with (
            patch.object(engine, "_load_piper") as mock_load,
            patch("tts_engine.sintetizza_piper", return_value=fake_wav),
            patch("tts_engine._wav_to_mp3_bytes", return_value=fake_mp3),
        ):
            # Act
            result = engine._synthesize(0, "paola")

        # Assert
        assert result == fake_mp3
        mock_load.assert_called_once()


# ===========================================================================
# Test — TTSEngine.save_all
# ===========================================================================


class TestSaveAll:
    def test_save_all_concatenates_all_paragraphs(self, engine):
        """save_all deve sintetizzare tutti i paragrafi e concatenarli."""
        # Arrange
        engine.load_text("Primo.\n\nSecondo.\n\nTerzo.", "test.md")

        call_count = 0

        def fake_get_audio(idx, voice, style):
            nonlocal call_count
            call_count += 1
            return f"mp3_{idx}".encode()

        with patch.object(engine, "get_audio", side_effect=fake_get_audio):
            # Act
            result = engine.save_all("giuseppe")

        # Assert
        assert call_count == 3
        assert result == b"mp3_0mp3_1mp3_2"


# ===========================================================================
# Test — TTSEngine.prefetch logging
# ===========================================================================


class TestPrefetchLogging:
    def test_prefetch_logs_warning_on_failure(self, engine):
        """Il prefetch deve loggare un warning quando la sintesi fallisce."""
        # Arrange
        engine.load_text("Paragrafo test.", "test.md")

        with (
            patch.object(engine, "_synthesize", side_effect=RuntimeError("boom")),
            patch("tts_engine.log") as mock_log,
        ):
            # Act
            engine.prefetch(0, "giuseppe")
            # Attendi che il thread pool esegua il task
            time.sleep(0.5)

        # Assert
        mock_log.warning.assert_called_once()
        args = mock_log.warning.call_args
        assert "Prefetch paragrafo" in args[0][0]


# ===========================================================================
# Test — /api/save come endpoint POST
# ===========================================================================


class TestSaveEndpointPost:
    def test_save_rejects_get(self, client):
        """GET /api/save deve restituire 405 Method Not Allowed."""
        # Act
        response = client.get("/api/save")

        # Assert
        assert response.status_code == 405

    def test_save_post_no_file_loaded(self, client):
        """POST /api/save senza file caricato deve restituire 400."""
        # Act
        response = client.post(
            "/api/save",
            data='{"voice": "giuseppe"}',
            content_type="application/json",
        )

        # Assert
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_save_post_invalid_voice(self, client):
        """POST /api/save con voce invalida deve restituire 400."""
        # Act
        response = client.post(
            "/api/save",
            data='{"voice": "nonexistent"}',
            content_type="application/json",
        )

        # Assert
        assert response.status_code == 400


# ===========================================================================
# Test — TTSEngine._load_piper double-checked locking
# ===========================================================================


class TestLoadPiper:
    def test_load_piper_called_once_with_concurrent_threads(self, engine):
        """_load_piper deve caricare il modello una sola volta anche con thread concorrenti."""
        # Arrange
        load_count = 0

        def counting_load():
            nonlocal load_count
            # Simula _load_piper senza caricare davvero il modello
            with engine._lock:
                if engine._piper_voice is not None:
                    return
                load_count += 1
                time.sleep(0.1)  # Simula tempo di caricamento
                engine._piper_voice = MagicMock()
                engine._piper_sample_rate = 22050

        with patch.object(engine, "_load_piper", side_effect=counting_load):
            # Act — 5 thread concorrenti che chiamano tutti _load_piper
            threads = []
            for _ in range(5):
                t = threading.Thread(target=engine._load_piper)
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

        # Assert — il modello deve essere stato caricato una sola volta
        assert load_count == 1
