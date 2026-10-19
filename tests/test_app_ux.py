"""
tests/test_app_ux.py
Behavior tests for the API changes that make the web UI usable without
technical knowledge: readable error messages, accepted file names, recovery hints.
"""

import io
from unittest.mock import patch


def _upload(client, name: str, content: bytes = b"Testo di prova."):
    return client.post(
        "/api/load?lang=it",
        data={"file": (io.BytesIO(content), name)},
        content_type="multipart/form-data",
    )


class TestLoadFileNames:
    def test_load_name_with_parentheses_is_accepted(self, client):
        response = _upload(client, "documento (1).md")

        assert response.status_code == 200
        assert response.get_json()["filename"] == "documento (1).md"

    def test_load_name_with_forbidden_chars_explains_the_name(self, client):
        response = _upload(client, "file;rm.md")

        assert response.status_code == 400
        error = response.get_json()["error"]
        assert "nome del file" in error
        assert "Formato non supportato" not in error

    def test_load_unsupported_extension_still_says_format(self, client):
        response = _upload(client, "dati.csv")

        assert response.status_code == 400
        assert "Formato non supportato" in response.get_json()["error"]


class TestLoadUnreadableFile:
    def test_load_corrupted_pdf_returns_readable_json_error(self, client):
        response = _upload(client, "rotto.pdf", b"non sono un pdf")

        assert response.status_code == 422
        error = response.get_json()["error"]
        assert "Non riesco ad aprire" in error


class TestLoadFileWithoutText:
    def test_load_empty_file_explains_there_is_no_text(self, client):
        response = _upload(client, "vuoto.txt", b"")

        assert response.status_code == 422
        assert "non ho trovato testo" in response.get_json()["error"]

    def test_load_whitespace_only_file_explains_there_is_no_text(self, client):
        response = _upload(client, "spazi.txt", b"   \n\n  \n")

        assert response.status_code == 422

    def test_load_file_with_text_still_succeeds(self, client):
        response = _upload(client, "ok.txt", b"Una riga.")

        assert response.status_code == 200
        assert response.get_json()["total"] == 1


def _load_document(client):
    from src import app as flask_app

    flask_app.engine._paragraphs = ["Primo paragrafo.", "Secondo paragrafo."]
    flask_app.engine._filename = "capitolo.md"


class TestOnlineVoiceFailure:
    def test_audio_with_failing_online_voice_names_voice_and_offers_offline(self, client):
        _load_document(client)
        with patch("src.app.engine.get_audio", side_effect=OSError("403")):
            response = client.get("/api/audio/0?voice=giuseppe&style=neutro&lang=it")

        assert response.status_code == 503
        data = response.get_json()
        assert "Giuseppe" in data["error"]
        assert data["fallback_voice"] == "paola"

    def test_audio_with_failing_offline_voice_has_no_fallback(self, client):
        _load_document(client)
        with patch("src.app.engine.get_audio", side_effect=OSError("ffmpeg")):
            response = client.get("/api/audio/0?voice=paola&style=neutro&lang=it")

        assert response.status_code == 500
        assert "fallback_voice" not in response.get_json()

    def test_save_with_failing_online_voice_returns_json_with_fallback(self, client):
        _load_document(client)
        with patch("src.app.engine.save_all", side_effect=OSError("403")):
            response = client.post("/api/save?lang=it", json={"voice": "giuseppe"})

        assert response.status_code == 503
        data = response.get_json()
        assert "Giuseppe" in data["error"]
        assert data["fallback_voice"] == "paola"


class TestDefaultVoiceAvailability:
    def test_voices_default_is_offline_when_online_voices_are_down(self, client):
        with patch("src.app.engine.is_online_available", return_value=False):
            data = client.get("/api/voices").get_json()

        assert data["online_available"] is False
        assert data["default"] == "paola"

    def test_voices_default_stays_online_when_reachable(self, client):
        with patch("src.app.engine.is_online_available", return_value=True):
            data = client.get("/api/voices").get_json()

        assert data["online_available"] is True
        assert data["default"] == "giuseppe"
