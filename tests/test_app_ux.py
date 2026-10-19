"""
tests/test_app_ux.py
Behavior tests for the API changes that make the web UI usable without
technical knowledge: readable error messages, accepted file names, recovery hints.
"""

import io


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
