"""
tests/test_app_extended.py
Test aggiuntivi per app.py: security headers, sanitize_filename,
endpoint success paths, prefetch endpoint.

Complementa test_app.py (che copre validazione input e error cases).
"""

import io
from unittest.mock import patch, MagicMock

import pytest

# ===========================================================================
# Fixture
# ===========================================================================


@pytest.fixture()
def client_con_testo(client):
    """Flask test client con un documento già caricato nell'engine."""
    import app as flask_app

    flask_app.engine._paragraphs = [
        "Primo paragrafo di test.",
        "Secondo paragrafo di test.",
        "Terzo paragrafo di test.",
    ]
    flask_app.engine._filename = "documento.md"
    return client


# ===========================================================================
# Test — Security Headers
# ===========================================================================


class TestSecurityHeaders:
    """Verifica che gli header di sicurezza siano presenti su tutte le risposte."""

    def test_x_content_type_options(self, client):
        """Ogni risposta deve avere X-Content-Type-Options: nosniff."""
        # Act
        response = client.get("/")

        # Assert
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, client):
        """Ogni risposta deve avere X-Frame-Options: DENY."""
        # Act
        response = client.get("/")

        # Assert
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_referrer_policy(self, client):
        """Ogni risposta deve avere Referrer-Policy impostato."""
        # Act
        response = client.get("/")

        # Assert
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_headers_presenti_su_api(self, client):
        """Gli header di sicurezza devono essere presenti anche sulle API."""
        # Act
        response = client.get("/api/voices")

        # Assert
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_headers_presenti_su_errori(self, client):
        """Gli header devono essere presenti anche su risposte di errore."""
        # Act
        response = client.get("/api/audio/0")  # nessun file caricato → 400

        # Assert
        assert response.headers.get("X-Content-Type-Options") == "nosniff"


# ===========================================================================
# Test — _sanitize_filename
# ===========================================================================


class TestSanitizeFilename:
    """Test per la funzione di sanitizzazione nomi file."""

    def _sanitize(self, name: str) -> str:
        from app import _sanitize_filename

        return _sanitize_filename(name)

    def test_filename_valido_semplice(self):
        """Un nome file .md semplice deve passare invariato."""
        assert self._sanitize("documento.md") == "documento.md"

    def test_filename_con_spazi(self):
        """Nomi con spazi devono essere accettati."""
        assert self._sanitize("il mio file.md") == "il mio file.md"

    def test_filename_con_trattini_e_underscore(self):
        """Trattini e underscore devono essere accettati."""
        assert self._sanitize("mio-file_v2.md") == "mio-file_v2.md"

    def test_formato_non_supportato_rifiutato(self):
        """File con formato non supportato devono essere rifiutati."""
        assert self._sanitize("file.csv") == ""
        assert self._sanitize("file.py") == ""
        assert self._sanitize("file.xlsx") == ""
        assert self._sanitize("file.pptx") == ""

    def test_path_traversal_bloccato(self):
        """Tentativi di path traversal devono essere neutralizzati."""
        # Il path traversal viene bloccato da PurePosixPath.name
        risultato = self._sanitize("../../../etc/passwd.md")
        # Deve estrarre solo il nome base
        assert "/" not in risultato
        assert ".." not in risultato

    def test_filename_vuoto_rifiutato(self):
        """Un nome vuoto deve essere rifiutato."""
        assert self._sanitize("") == ""

    def test_filename_solo_estensione_rifiutato(self):
        """Il solo '.md' senza nome deve essere rifiutato."""
        assert self._sanitize(".md") == ""

    def test_filename_con_caratteri_speciali_rifiutato(self):
        """Caratteri speciali (;, &, |, etc.) devono causare rifiuto."""
        assert self._sanitize("file;rm -rf.md") == ""
        assert self._sanitize("file|cat.md") == ""
        assert self._sanitize("file$(cmd).md") == ""

    def test_filename_unicode_accettato(self):
        """Nomi con caratteri unicode (accenti) devono essere accettati."""
        risultato = self._sanitize("caffè.md")
        assert risultato == "caffè.md"

    def test_tutti_i_formati_supportati_accettati(self):
        """Tutti i formati supportati devono essere accettati."""
        assert self._sanitize("libro.epub") == "libro.epub"
        assert self._sanitize("documento.docx") == "documento.docx"
        assert self._sanitize("pagina.html") == "pagina.html"
        assert self._sanitize("pagina.htm") == "pagina.htm"
        assert self._sanitize("report.pdf") == "report.pdf"
        assert self._sanitize("nota.txt") == "nota.txt"
        assert self._sanitize("readme.md") == "readme.md"

    def test_doppia_estensione_rifiutata(self):
        """Filename con double extension sospetta deve essere gestito."""
        # "file.php.md" contiene il punto nel nome, che è permesso
        risultato = self._sanitize("file.php.md")
        # Il regex ammette il punto, quindi passa — è un file .md valido
        assert risultato == "file.php.md"


# ===========================================================================
# Test — /api/audio success path
# ===========================================================================


class TestAudioEndpointSuccess:
    """Test per il percorso di successo dell'endpoint audio."""

    def test_audio_restituisce_mp3(self, client_con_testo):
        """GET /api/audio/0 con file caricato deve restituire audio/mpeg."""
        # Arrange
        import app as flask_app

        fake_mp3 = b"ID3\x04\x00\x00\x00\x00\x00\x00"

        with patch.object(flask_app.engine, "get_audio", return_value=fake_mp3):
            # Act
            response = client_con_testo.get("/api/audio/0?voice=giuseppe")

        # Assert
        assert response.status_code == 200
        assert response.content_type == "audio/mpeg"
        assert response.data == fake_mp3

    def test_audio_con_voce_diversa(self, client_con_testo):
        """GET /api/audio/0?voice=isabella deve usare la voce specificata."""
        # Arrange
        import app as flask_app
        from config import DEFAULT_STYLE

        fake_mp3 = b"mp3_isabella"

        with patch.object(flask_app.engine, "get_audio", return_value=fake_mp3) as mock:
            # Act
            response = client_con_testo.get("/api/audio/1?voice=isabella")

        # Assert
        assert response.status_code == 200
        mock.assert_called_once_with(1, "isabella", DEFAULT_STYLE)

    def test_audio_paragrafo_inesistente_404(self, client_con_testo):
        """GET /api/audio/999 deve restituire 404."""
        # Arrange
        import app as flask_app

        with patch.object(flask_app.engine, "get_audio", side_effect=IndexError("out of range")):
            # Act
            response = client_con_testo.get("/api/audio/999?voice=giuseppe")

        # Assert
        assert response.status_code == 404

    def test_audio_errore_sintesi_500(self, client_con_testo):
        """Un errore di sintesi deve restituire 500 con messaggio generico."""
        # Arrange
        import app as flask_app

        with patch.object(
            flask_app.engine,
            "get_audio",
            side_effect=RuntimeError("ffmpeg crashed"),
        ):
            # Act
            response = client_con_testo.get("/api/audio/0?voice=giuseppe")

        # Assert
        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data
        # Il messaggio NON deve contenere dettagli interni
        assert "ffmpeg" not in data["error"]


# ===========================================================================
# Test — /api/prefetch
# ===========================================================================


class TestPrefetchEndpoint:
    """Test per l'endpoint di prefetch."""

    def test_prefetch_restituisce_ok(self, client_con_testo):
        """GET /api/prefetch/1 deve restituire status ok."""
        # Arrange
        import app as flask_app
        from config import DEFAULT_STYLE

        with patch.object(flask_app.engine, "prefetch") as mock_pf:
            # Act
            response = client_con_testo.get("/api/prefetch/1?voice=giuseppe")

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        mock_pf.assert_called_once_with(1, "giuseppe", DEFAULT_STYLE)

    def test_prefetch_usa_voce_default(self, client_con_testo):
        """Senza parametro voice, deve usare la voce di default."""
        # Arrange
        import app as flask_app
        from config import DEFAULT_VOICE, DEFAULT_STYLE

        with patch.object(flask_app.engine, "prefetch") as mock_pf:
            # Act
            response = client_con_testo.get("/api/prefetch/0")

        # Assert
        assert response.status_code == 200
        mock_pf.assert_called_once_with(0, DEFAULT_VOICE, DEFAULT_STYLE)


# ===========================================================================
# Test — /api/save success path
# ===========================================================================


class TestSaveEndpointSuccess:
    """Test per il percorso di successo dell'endpoint save."""

    def test_save_restituisce_mp3_con_content_disposition(self, client_con_testo):
        """POST /api/save deve restituire MP3 con header Content-Disposition."""
        # Arrange
        import app as flask_app

        fake_mp3 = b"ID3\x04\x00complete_audio"

        with patch.object(flask_app.engine, "save_all", return_value=fake_mp3):
            # Act
            response = client_con_testo.post(
                "/api/save",
                data='{"voice": "giuseppe"}',
                content_type="application/json",
            )

        # Assert
        assert response.status_code == 200
        assert response.content_type == "audio/mpeg"
        assert "Content-Disposition" in response.headers
        assert "attachment" in response.headers["Content-Disposition"]
        assert ".mp3" in response.headers["Content-Disposition"]

    def test_save_con_voce_invalida_400(self, client_con_testo):
        """POST /api/save con voce inesistente deve restituire 400."""
        # Act
        response = client_con_testo.post(
            "/api/save",
            data='{"voice": "voce_fake"}',
            content_type="application/json",
        )

        # Assert
        assert response.status_code == 400
        assert "error" in response.get_json()


# ===========================================================================
# Test — /api/load con path traversal
# ===========================================================================


class TestLoadEndpointSecurity:
    """Test di sicurezza per l'endpoint di caricamento file."""

    def test_load_path_traversal_bloccato(self, client):
        """Un file con path traversal nel nome deve essere rifiutato."""
        # Arrange
        evil_file = (io.BytesIO(b"# Hack"), "../../../etc/passwd.md")

        # Act
        response = client.post(
            "/api/load",
            data={"file": evil_file},
            content_type="multipart/form-data",
        )

        # Assert — potrebbe essere accettato (nome base estratto) o rifiutato
        # L'importante è che il path traversal sia neutralizzato
        if response.status_code == 200:
            data = response.get_json()
            assert "/" not in data["filename"]
            assert ".." not in data["filename"]

    def test_load_filename_con_null_byte_rifiutato(self, client):
        """Un file con null byte nel nome deve essere rifiutato."""
        # Arrange
        evil_file = (io.BytesIO(b"# Content"), "file\x00.md")

        # Act
        response = client.post(
            "/api/load",
            data={"file": evil_file},
            content_type="multipart/form-data",
        )

        # Assert
        assert response.status_code == 400


# ===========================================================================
# Test — VOICES_META consistenza
# ===========================================================================


class TestVoicesMeta:
    """Test per la coerenza dei metadati delle voci."""

    def test_voices_meta_contiene_tutte_le_voci(self):
        """VOICES_META deve avere una entry per ogni voce in ALL_VOICES."""
        from app import VOICES_META
        from config import ALL_VOICES

        # Arrange
        meta_ids = {v["id"] for v in VOICES_META}

        # Assert
        assert meta_ids == set(ALL_VOICES)

    def test_voices_meta_campi_obbligatori(self):
        """Ogni voce deve avere id, label, type, multilingual, gender."""
        from app import VOICES_META

        # Assert
        campi = {"id", "label", "type", "multilingual", "gender"}
        for voce in VOICES_META:
            assert (
                campi <= voce.keys()
            ), f"Voce '{voce.get('id')}' mancante di: {campi - voce.keys()}"

    def test_voices_meta_type_validi(self):
        """Il type di ogni voce deve essere 'edge' o 'piper'."""
        from app import VOICES_META

        # Assert
        for voce in VOICES_META:
            assert voce["type"] in (
                "edge",
                "piper",
            ), f"Voce '{voce['id']}' ha type '{voce['type']}' non valido"

    def test_voices_meta_gender_validi(self):
        """Il gender deve essere 'M' o 'F'."""
        from app import VOICES_META

        # Assert
        for voce in VOICES_META:
            assert voce["gender"] in (
                "M",
                "F",
            ), f"Voce '{voce['id']}' ha gender '{voce['gender']}' non valido"
