"""
tests/test_app.py
Test suite per TTS Reader: leggi_markdown, app (Flask), tts_engine.

Dipendenze esterne (edge-tts, piper, ffmpeg) sono sempre mockata
per garantire test isolati e veloci.
"""

import io
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Patch globale: impedisce che leggi_markdown tenti import di edge_tts/piper
# a livello di modulo durante il caricamento dei test.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent))


# ===========================================================================
# Test — leggi_markdown.py
# ===========================================================================

class TestMarkdownATesto:
    """Test per la funzione markdown_a_testo (fallback regex, senza pandoc)."""

    def _converti(self, markdown: str) -> str:
        """Helper: esegue markdown_a_testo su testo inline (via file temp)."""
        from leggi_markdown import markdown_a_testo

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(markdown)
            tmp_path = Path(f.name)

        try:
            # Forza percorso pandoc assente per usare il fallback regex
            with patch("shutil.which", return_value=None):
                return markdown_a_testo(tmp_path)
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

@pytest.fixture()
def client():
    """Crea un Flask test client con engine resettato a ogni test."""
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    # Resetta lo stato interno dell'engine tra i test
    flask_app.engine._paragraphs = []
    flask_app.engine._filename = ""
    flask_app.engine._cache.clear()

    with flask_app.app.test_client() as c:
        yield c


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
                f"Voce {voce.get('id')} mancante di campi: "
                f"{campi_obbligatori - voce.keys()}"
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

    def test_load_non_md_file(self, client):
        """POST /api/load con file .txt deve restituire 400."""
        # Arrange
        file_txt = (io.BytesIO(b"testo semplice"), "documento.txt")

        # Act
        response = client.post(
            "/api/load",
            data={"file": file_txt},
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
        """GET /api/save senza file caricato deve restituire 400."""
        # Arrange — engine senza paragrafi (resettato dal fixture)

        # Act
        response = client.get("/api/save")

        # Assert
        assert response.status_code == 400
        assert "error" in response.get_json()


# ===========================================================================
# Test — tts_engine.py
# ===========================================================================

@pytest.fixture()
def engine():
    """Crea un TTSEngine fresco per ogni test."""
    from tts_engine import TTSEngine

    return TTSEngine()


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

        def fake_synthesize(index, voice):
            return mp3_giuseppe if voice == "giuseppe" else mp3_isabella

        with patch.object(engine, "_synthesize", side_effect=fake_synthesize):
            # Act
            audio_giuseppe = engine.get_audio(0, "giuseppe")
            audio_isabella = engine.get_audio(0, "isabella")

        # Assert — risultati distinti per voce diversa
        assert audio_giuseppe == mp3_giuseppe
        assert audio_isabella == mp3_isabella
        assert audio_giuseppe != audio_isabella
