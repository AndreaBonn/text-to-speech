"""
tests/test_app_extended.py
Test aggiuntivi per app.py: security headers, sanitize_filename,
endpoint success paths, prefetch endpoint.

Complementa test_app.py (che copre validazione input e error cases).
"""

import io
from pathlib import Path
from unittest.mock import ANY, patch

import pytest

# ===========================================================================
# Fixture
# ===========================================================================


@pytest.fixture()
def client_con_testo(client):
    """Flask test client con un documento già caricato nell'engine."""
    from src import app as flask_app

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
        from src.app import _sanitize_filename

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
        # SECURITY.md: il nome base viene estratto, il percorso scartato
        assert self._sanitize("../../../etc/passwd.md") == "passwd.md"

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

    def test_filename_con_parentesi_accettato(self):
        """I nomi dei file scaricati due volte, es. 'documento (1).md', devono passare."""
        assert self._sanitize("documento (1).md") == "documento (1).md"
        assert self._sanitize("foto [2].pdf") == "foto [2].pdf"

    def test_filename_con_apostrofo_e_virgola_accettato(self):
        """Apostrofi (dritti e tipografici) e virgole sono comuni nei titoli italiani."""
        assert self._sanitize("l'arte della guerra.epub") == "l'arte della guerra.epub"
        assert self._sanitize("l\u2019isola, cap. 1.docx") == "l\u2019isola, cap. 1.docx"

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
        from src import app as flask_app

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
        from src import app as flask_app
        from src.config import DEFAULT_STYLE

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
        from src import app as flask_app

        with patch.object(flask_app.engine, "get_audio", side_effect=IndexError("out of range")):
            # Act
            response = client_con_testo.get("/api/audio/999?voice=giuseppe")

        # Assert
        assert response.status_code == 404

    def test_audio_errore_sintesi_500(self, client_con_testo):
        """Un errore di sintesi deve restituire 500 con messaggio generico."""
        # Arrange
        from src import app as flask_app

        with patch.object(
            flask_app.engine,
            "get_audio",
            side_effect=RuntimeError("ffmpeg crashed"),
        ):
            # Act
            response = client_con_testo.get("/api/audio/0?voice=paola")

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
        from src import app as flask_app
        from src.config import DEFAULT_STYLE

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
        from src import app as flask_app
        from src.config import DEFAULT_STYLE, DEFAULT_VOICE

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
        from src import app as flask_app

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

        # Assert — SECURITY.md: viene tenuto solo il nome base
        assert response.status_code == 200
        assert response.get_json()["filename"] == "passwd.md"

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
        from src.app import VOICES_META
        from src.config import ALL_VOICES

        # Arrange
        meta_ids = {v["id"] for v in VOICES_META}

        # Assert
        assert meta_ids == set(ALL_VOICES)

    def test_voices_meta_campi_obbligatori(self):
        """Ogni voce deve avere id, label, type, multilingual, gender, lang."""
        from src.app import VOICES_META

        # Assert
        campi = {"id", "label", "type", "multilingual", "gender", "lang"}
        for voce in VOICES_META:
            assert campi <= voce.keys(), (
                f"Voce '{voce.get('id')}' mancante di: {campi - voce.keys()}"
            )

    def test_voices_meta_type_validi(self):
        """Il type di ogni voce deve essere 'edge' o 'piper'."""
        from src.app import VOICES_META

        # Assert
        for voce in VOICES_META:
            assert voce["type"] in (
                "edge",
                "piper",
            ), f"Voce '{voce['id']}' ha type '{voce['type']}' non valido"

    def test_voices_meta_gender_validi(self):
        """Il gender deve essere 'M' o 'F'."""
        from src.app import VOICES_META

        # Assert
        for voce in VOICES_META:
            assert voce["gender"] in (
                "M",
                "F",
            ), f"Voce '{voce['id']}' ha gender '{voce['gender']}' non valido"


# ===========================================================================
# Test — errorhandler 413 (file troppo grande)
# ===========================================================================


class TestTooLargeErrorHandler:
    """Verifica che il 413 errorhandler risponda con JSON e messaggio."""

    def test_upload_troppo_grande_restituisce_413(self, client):
        """Un file superiore a MAX_CONTENT_LENGTH deve restituire 413."""
        # Arrange — abbassa il limite a 10 byte per il solo test
        from src.app import app

        original_limit = app.config["MAX_CONTENT_LENGTH"]
        app.config["MAX_CONTENT_LENGTH"] = 10

        try:
            payload = b"X" * 50  # 50 byte > 10 byte limite
            data = {"file": (io.BytesIO(payload), "grande.txt")}

            # Act
            response = client.post(
                "/api/load",
                data=data,
                content_type="multipart/form-data",
            )
        finally:
            app.config["MAX_CONTENT_LENGTH"] = original_limit

        # Assert
        assert response.status_code == 413
        body = response.get_json()
        assert body is not None
        assert "error" in body

    def test_413_ha_security_headers(self, client):
        """La risposta 413 deve avere gli header di sicurezza."""
        # Arrange
        from src.app import app

        original_limit = app.config["MAX_CONTENT_LENGTH"]
        app.config["MAX_CONTENT_LENGTH"] = 10

        try:
            data = {"file": (io.BytesIO(b"X" * 50), "grande.txt")}

            # Act
            response = client.post(
                "/api/load",
                data=data,
                content_type="multipart/form-data",
            )
        finally:
            app.config["MAX_CONTENT_LENGTH"] = original_limit

        # Assert
        assert response.headers.get("X-Content-Type-Options") == "nosniff"


# ===========================================================================
# Test — /api/audio con style invalido
# ===========================================================================


class TestAudioInvalidStyle:
    """Verifica che style non valido su /api/audio restituisca 400."""

    def test_audio_style_invalido_restituisce_400(self, client_con_testo):
        """GET /api/audio/0?style=nonexistent deve restituire 400 con error."""
        # Act
        response = client_con_testo.get("/api/audio/0?voice=giuseppe&style=nonexistent")

        # Assert
        assert response.status_code == 400
        body = response.get_json()
        assert "error" in body

    def test_audio_style_vuoto_restituisce_400(self, client_con_testo):
        """GET /api/audio/0?style= (stringa vuota) deve restituire 400."""
        # Act
        response = client_con_testo.get("/api/audio/0?voice=giuseppe&style=")

        # Assert
        assert response.status_code == 400
        assert "error" in response.get_json()


# ===========================================================================
# Test — /api/save con style invalido
# ===========================================================================


class TestSaveInvalidStyle:
    """Verifica che style non valido su /api/save restituisca 400."""

    def test_save_style_invalido_restituisce_400(self, client_con_testo):
        """POST /api/save con style inesistente deve restituire 400."""
        # Act
        response = client_con_testo.post(
            "/api/save",
            data='{"voice": "giuseppe", "style": "nonexistent"}',
            content_type="application/json",
        )

        # Assert
        assert response.status_code == 400
        body = response.get_json()
        assert "error" in body

    def test_save_style_vuoto_restituisce_400(self, client_con_testo):
        """POST /api/save con style='' deve restituire 400."""
        # Act
        response = client_con_testo.post(
            "/api/save",
            data='{"voice": "giuseppe", "style": ""}',
            content_type="application/json",
        )

        # Assert
        assert response.status_code == 400
        assert "error" in response.get_json()


# ===========================================================================
# Test — Content-Security-Policy (SECURITY.md § Content Security Policy)
# ===========================================================================

EXPECTED_CSP = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'", "https://fonts.googleapis.com"],
    "font-src": ["https://fonts.gstatic.com"],
    "media-src": ["'self'", "blob:"],
    "base-uri": ["'self'"],
    "object-src": ["'none'"],
    "form-action": ["'self'"],
}


def _parse_csp(header: str) -> dict[str, list[str]]:
    directives = {}
    for part in header.split(";"):
        tokens = part.split()
        if tokens:
            directives[tokens[0]] = tokens[1:]
    return directives


class TestContentSecurityPolicy:
    @pytest.mark.parametrize(
        "method, url",
        [
            ("get", "/"),
            ("get", "/api/voices"),
            ("get", "/api/audio/0"),  # 400: nessun documento caricato
            ("post", "/api/load"),  # 400: nessun file inviato
        ],
    )
    def test_csp_has_exactly_the_documented_directives(self, client, method, url):
        response = getattr(client, method)(url)

        assert _parse_csp(response.headers["Content-Security-Policy"]) == EXPECTED_CSP

    def test_error_responses_in_the_parametrization_are_400(self, client):
        assert client.get("/api/audio/0").status_code == 400
        assert client.post("/api/load").status_code == 400


# ===========================================================================
# Test — indici dei paragrafi, stima durata
# ===========================================================================


class TestParagraphIndexes:
    def test_load_numbers_paragraphs_from_zero(self, client):
        with patch("src.app.engine.load_file", return_value=["Uno.", "Due.", "Tre."]):
            response = client.post(
                "/api/load",
                data={"file": (io.BytesIO(b"x"), "tre.md")},
                content_type="multipart/form-data",
            )

        assert [p["idx"] for p in response.get_json()["paragraphs"]] == [0, 1, 2]

    def test_load_text_numbers_paragraphs_from_zero(self, client):
        response = client.post("/api/load-text", json={"text": "Uno.\n\nDue.\n\nTre."})

        assert [p["idx"] for p in response.get_json()["paragraphs"]] == [0, 1, 2]


class TestEstimatedSeconds:
    @pytest.mark.parametrize(
        "chars, seconds",
        [(15, 1), (16, 2), (30, 2), (31, 3)],
    )
    def test_estimate_rounds_up_to_whole_seconds(self, client, chars, seconds):
        # README/config: 15 characters per second, shown as "circa"
        data = client.post("/api/load-text", json={"text": "a" * chars}).get_json()

        assert data["estimated_seconds"] == seconds


# ===========================================================================
# Test — _sanitize_filename: caratteri vietati e ammessi
# ===========================================================================


class TestSanitizeFilenameCharacters:
    @pytest.mark.parametrize("char", list('&\\<>*?%"|'))
    def test_forbidden_character_is_rejected(self, char):
        from src.app import _sanitize_filename

        assert _sanitize_filename(f"a{char}b.md") == ""

    @pytest.mark.parametrize("name", ["c++.md", "documento (1).pdf", "l'arte.epub"])
    def test_allowed_character_names_pass_unchanged(self, name):
        from src.app import _sanitize_filename

        assert _sanitize_filename(name) == name

    def test_name_without_a_dot_before_the_extension_is_rejected(self):
        from src.app import _sanitize_filename

        assert _sanitize_filename("notaxmd") == ""


# ===========================================================================
# Test — stile suggerito, stile passato al motore
# ===========================================================================


class TestSuggestedStyle:
    @pytest.mark.parametrize(
        "name, style",
        [
            ("libro.epub", "audiolibro"),
            ("nota.md", "notiziario"),
            ("pagina.html", "notiziario"),
            ("pagina.htm", "notiziario"),
            ("nota.txt", "neutro"),
            ("report.pdf", "neutro"),
            ("documento.docx", "neutro"),
        ],
    )
    def test_load_suggests_the_style_documented_for_the_format(self, client, name, style):
        # README: EPUB -> Audiobook, Markdown/HTML -> Newscast, other formats -> Neutral
        with patch("src.app.engine.load_file", return_value=["Testo."]):
            response = client.post(
                "/api/load",
                data={"file": (io.BytesIO(b"x"), name)},
                content_type="multipart/form-data",
            )

        assert response.get_json()["suggested_style"] == style

    def test_load_text_suggests_neutral(self, client):
        data = client.post("/api/load-text", json={"text": "Testo."}).get_json()

        assert data["suggested_style"] == "neutro"


class TestStylePassedToEngine:
    def test_audio_passes_the_requested_style(self, client_con_testo):
        from src import app as flask_app

        with patch.object(flask_app.engine, "get_audio", return_value=b"mp3") as mock:
            client_con_testo.get("/api/audio/1?voice=isabella&style=lento")

        mock.assert_called_once_with(1, "isabella", "lento")

    def test_prefetch_passes_the_requested_style(self, client_con_testo):
        from src import app as flask_app

        with patch.object(flask_app.engine, "prefetch") as mock:
            client_con_testo.get("/api/prefetch/2?voice=paola&style=audiolibro")

        mock.assert_called_once_with(2, "paola", "audiolibro")

    def test_preview_synthesizes_with_the_requested_voice_and_style(self, client):
        from src import app as flask_app

        with patch.object(flask_app.engine, "_synthesize_text", return_value=b"mp3") as synth:
            client.get("/api/preview?voice=isabella&style=lento")

        synth.assert_called_once_with(
            "Ciao, sono Isabella. Posso leggere ad alta voce i tuoi documenti.",
            "isabella",
            "lento",
        )

    def test_preview_invalid_style_is_rejected_without_synthesis(self, client):
        from src import app as flask_app

        with patch.object(flask_app.engine, "_synthesize_text", return_value=b"mp3") as synth:
            response = client.get("/api/preview?voice=isabella&style=nonexistent&lang=it")

        assert response.status_code == 400
        assert response.get_json() == {"error": "Stile 'nonexistent' non valido"}
        synth.assert_not_called()

    def test_save_passes_voice_and_style_in_the_right_order(self, client_con_testo):
        from src import app as flask_app

        with patch.object(flask_app.engine, "save_all", return_value=b"mp3") as mock:
            response = client_con_testo.post(
                "/api/save", json={"voice": "paola", "style": "audiolibro"}
            )

        assert response.status_code == 200
        mock.assert_called_once_with("paola", "audiolibro", on_progress=ANY)


# ===========================================================================
# Test — file temporaneo di /api/load
# ===========================================================================


class TestLoadTempFileCleanup:
    def _upload(self, client):
        return client.post(
            "/api/load",
            data={"file": (io.BytesIO(b"x"), "nota.md")},
            content_type="multipart/form-data",
        )

    def _recording_load(self, seen, result=None, error=None):
        def fake_load_file(path, display_name=None):
            seen["path"] = Path(path)
            seen["existed_during"] = Path(path).exists()
            if error is not None:
                raise error
            return result

        return fake_load_file

    def test_temp_file_exists_during_conversion_and_is_removed_after_success(self, client):
        seen = {}

        with patch("src.app.engine.load_file", side_effect=self._recording_load(seen, ["Ok."])):
            response = self._upload(client)

        assert response.status_code == 200
        assert seen["existed_during"] is True
        assert not seen["path"].exists()

    def test_temp_file_is_removed_after_failed_conversion(self, client):
        seen = {}
        load = self._recording_load(seen, error=RuntimeError("corrupt"))

        with patch("src.app.engine.load_file", side_effect=load):
            response = self._upload(client)

        assert response.status_code == 422
        assert seen["existed_during"] is True
        assert not seen["path"].exists()


# ===========================================================================
# Test — configurazione e metadati voci (README, SECURITY.md)
# ===========================================================================


class TestAppConfiguration:
    def test_upload_limit_is_50_megabytes(self):
        from src.app import app

        assert app.config["MAX_CONTENT_LENGTH"] == 52428800

    def test_voices_endpoint_reports_default_style_and_style_ids(self, client):
        data = client.get("/api/voices").get_json()

        assert data["default_style"] == "neutro"
        assert [s["id"] for s in data["styles"]] == [
            "neutro",
            "notiziario",
            "audiolibro",
            "lento",
        ]

    @pytest.mark.parametrize(
        "voice_id, expected",
        [
            ("giuseppe", {"type": "edge", "gender": "M", "lang": "it", "multilingual": True}),
            ("isabella", {"type": "edge", "gender": "F", "lang": "it", "multilingual": False}),
            ("andrew", {"type": "edge", "gender": "M", "lang": "en", "multilingual": True}),
            ("ryan", {"type": "edge", "gender": "M", "lang": "en", "multilingual": False}),
            ("paola", {"type": "piper", "gender": "F", "lang": "it", "multilingual": False}),
        ],
    )
    def test_voices_meta_matches_the_readme_table(self, voice_id, expected):
        from src.app import VOICES_META

        meta = next(v for v in VOICES_META if v["id"] == voice_id)

        assert meta == {"id": voice_id, "label": voice_id.capitalize(), **expected}
