"""
tests/test_i18n.py
Test suite per il sistema di internazionalizzazione (i18n).

Copre: translations.py (get_lang, tr, get_styles_meta)
       e gli endpoint API con parametro ?lang=.
"""

import string
from unittest.mock import MagicMock

from src.translations import (
    DEFAULT_LANG,
    TRANSLATIONS,
    get_lang,
    get_styles_meta,
    tr,
)

# ===========================================================================
# Test — translations.get_lang()
# ===========================================================================


class TestGetLang:
    """Determina la lingua dalla richiesta HTTP."""

    def _make_request(self, lang_param="", accept_language=""):
        """Crea un mock di Flask request con query param e header."""
        req = MagicMock()
        req.args = {"lang": lang_param} if lang_param else {}
        req.headers = {"Accept-Language": accept_language} if accept_language else {}
        return req

    def test_default_senza_indicazioni(self):
        """Senza param né header deve restituire la lingua di default."""
        # Arrange
        req = self._make_request()

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == DEFAULT_LANG

    def test_query_param_it(self):
        """?lang=it deve restituire 'it'."""
        # Arrange
        req = self._make_request(lang_param="it")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == "it"

    def test_query_param_en(self):
        """?lang=en deve restituire 'en'."""
        # Arrange
        req = self._make_request(lang_param="en")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == "en"

    def test_query_param_case_insensitive(self):
        """?lang=EN (maiuscolo) deve restituire 'en'."""
        # Arrange
        req = self._make_request(lang_param="EN")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == "en"

    def test_query_param_lingua_non_supportata(self):
        """?lang=fr (non supportata) deve cadere sul default."""
        # Arrange
        req = self._make_request(lang_param="fr")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == DEFAULT_LANG

    def test_accept_language_header_it(self):
        """Accept-Language: it-IT deve restituire 'it'."""
        # Arrange
        req = self._make_request(accept_language="it-IT,it;q=0.9")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == "it"

    def test_accept_language_header_en(self):
        """Accept-Language: en-US,en;q=0.9 deve restituire 'en'."""
        # Arrange
        req = self._make_request(accept_language="en-US,en;q=0.9")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == "en"

    def test_accept_language_regione_da_sola_riconosce_en(self):
        """Accept-Language: en-US (solo codice regionale) deve restituire 'en'."""
        # Arrange
        req = self._make_request(accept_language="en-US")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == "en"

    def test_accept_language_salta_lingue_non_supportate(self):
        """Accept-Language: fr,en;q=0.8 deve scegliere la prima supportata ('en')."""
        # Arrange
        req = self._make_request(accept_language="fr,en;q=0.8")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == "en"

    def test_accept_language_header_fallback(self):
        """Accept-Language: fr-FR (non supportata) deve cadere sul default."""
        # Arrange
        req = self._make_request(accept_language="fr-FR,fr;q=0.9")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == DEFAULT_LANG

    def test_query_param_ha_priorita_su_header(self):
        """Il parametro ?lang= deve avere priorità sull'header Accept-Language."""
        # Arrange
        req = self._make_request(lang_param="en", accept_language="it-IT")

        # Act
        lang = get_lang(req)

        # Assert
        assert lang == "en"


# ===========================================================================
# Test — translations.tr()
# ===========================================================================


class TestTr:
    """Traduzione con interpolazione e fallback."""

    def test_traduzione_it(self):
        """tr() con lingua 'it' deve restituire il messaggio italiano."""
        # Act
        msg = tr("it", "error.no_file")

        # Assert
        assert msg == "Nessun file inviato"

    def test_traduzione_en(self):
        """tr() con lingua 'en' deve restituire il messaggio inglese."""
        # Act
        msg = tr("en", "error.no_file")

        # Assert
        assert msg == "No file provided"

    def test_interpolazione_singola(self):
        """tr() deve interpolare correttamente un parametro."""
        # Act
        msg = tr("it", "error.invalid_voice", voice="mario")

        # Assert
        assert "mario" in msg
        assert "{voice}" not in msg

    def test_interpolazione_multipla(self):
        """tr() deve interpolare più parametri."""
        # Act
        msg = tr("en", "error.unsupported_format", formats=".md, .txt")

        # Assert
        assert ".md, .txt" in msg
        assert "{formats}" not in msg

    def test_fallback_lingua_sconosciuta(self):
        """tr() con lingua non supportata deve usare il default."""
        # Act
        msg = tr("fr", "error.no_file")

        # Assert
        assert msg == "Nessun file inviato"

    def test_chiave_inesistente(self):
        """tr() con chiave inesistente deve restituire la chiave stessa."""
        # Act
        msg = tr("it", "error.chiave_fantasma")

        # Assert
        assert msg == "error.chiave_fantasma"

    def test_chiave_mancante_in_lingua_ripiega_sul_default(self, monkeypatch):
        """Chiave assente in 'en' ma presente in 'it': testo italiano, non la chiave."""
        # Arrange
        en_senza_chiave = {k: v for k, v in TRANSLATIONS["en"].items() if k != "error.no_file"}
        monkeypatch.setitem(TRANSLATIONS, "en", en_senza_chiave)

        # Act
        msg = tr("en", "error.no_file")

        # Assert
        assert msg == "Nessun file inviato"

    def test_tutte_le_chiavi_esistono_in_entrambe_le_lingue(self):
        """Ogni chiave in 'it' deve esistere anche in 'en' e viceversa."""
        # Arrange
        chiavi_it = {k for k in TRANSLATIONS["it"] if k != "styles"}
        chiavi_en = {k for k in TRANSLATIONS["en"] if k != "styles"}

        # Assert
        assert chiavi_it == chiavi_en, (
            f"Chiavi mancanti — solo in IT: {chiavi_it - chiavi_en}, "
            f"solo in EN: {chiavi_en - chiavi_it}"
        )

    def test_placeholder_uguali_per_chiave_in_it_e_en(self):
        """Ogni chiave espone gli stessi placeholder ({voice}, {formats}...) in IT e EN."""

        def campi(testo):
            return {nome for _, nome, _, _ in string.Formatter().parse(testo) if nome}

        # Arrange
        chiavi = [k for k in TRANSLATIONS["it"] if k != "styles"]

        # Assert
        for chiave in chiavi:
            assert campi(TRANSLATIONS["it"][chiave]) == campi(TRANSLATIONS["en"][chiave]), chiave
        assert campi(TRANSLATIONS["it"]["error.invalid_voice"]) == {"voice"}
        assert campi(TRANSLATIONS["en"]["error.unsupported_format"]) == {"formats"}


# ===========================================================================
# Test — translations.get_styles_meta()
# ===========================================================================


class TestGetStylesMeta:
    """Metadati stili tradotti per lingua."""

    def test_stili_it_hanno_label_e_description(self):
        """Ogni stile in italiano deve avere id, label, description."""
        # Act
        stili = get_styles_meta("it")

        # Assert
        assert len(stili) == 4
        for s in stili:
            assert "id" in s
            assert "label" in s
            assert "description" in s
            assert s["label"]  # non vuoto
            assert s["description"]  # non vuoto

    def test_stili_en_hanno_label_e_description(self):
        """Ogni stile in inglese deve avere id, label, description."""
        # Act
        stili = get_styles_meta("en")

        # Assert
        assert len(stili) == 4
        for s in stili:
            assert "id" in s
            assert "label" in s
            assert "description" in s

    def test_stili_label_e_description_letterali_it_e_en(self):
        """Label e description di uno stile coincidono con la specifica di prodotto."""
        # Act
        it = {s["id"]: s for s in get_styles_meta("it")}
        en = {s["id"]: s for s in get_styles_meta("en")}

        # Assert
        assert it["lento"] == {
            "id": "lento",
            "label": "Lento",
            "description": "Ritmo molto lento, per studio o comprensione",
        }
        assert en["lento"] == {
            "id": "lento",
            "label": "Slow",
            "description": "Very slow pace, for study or comprehension",
        }
        assert it["notiziario"]["description"] == (
            "Ritmo sostenuto e tono energico, come uno speaker"
        )
        assert en["notiziario"]["description"] == (
            "Fast pace and energetic tone, like a news anchor"
        )

    def test_stili_it_diversi_da_en(self):
        """Le label IT e EN devono essere diverse (tradotte)."""
        # Act
        stili_it = {s["id"]: s["label"] for s in get_styles_meta("it")}
        stili_en = {s["id"]: s["label"] for s in get_styles_meta("en")}

        # Assert — almeno uno stile deve avere label diversa
        differenze = [sid for sid in stili_it if stili_it[sid] != stili_en[sid]]
        assert len(differenze) > 0

    def test_stili_ids_consistenti(self):
        """Gli ID degli stili devono essere gli stessi in entrambe le lingue."""
        # Act
        ids_it = {s["id"] for s in get_styles_meta("it")}
        ids_en = {s["id"] for s in get_styles_meta("en")}

        # Assert
        attesi = {"neutro", "notiziario", "audiolibro", "lento"}
        assert ids_it == attesi
        assert ids_en == attesi

    def test_stili_lingua_non_supportata_usa_default(self):
        """get_styles_meta con lingua non supportata deve usare il default."""
        # Act
        stili_fr = get_styles_meta("fr")

        # Assert
        neutro = next(s for s in stili_fr if s["id"] == "neutro")
        assert neutro["label"] == "Neutro"
        assert neutro["description"] == "Lettura standard, bilanciata"


# ===========================================================================
# Test — Endpoint API con parametro ?lang=
# ===========================================================================


class TestEndpointI18n:
    """Verifica che gli endpoint restituiscano messaggi nella lingua richiesta."""

    def test_voices_stili_in_italiano(self, client):
        """GET /api/voices?lang=it deve restituire stili con label italiane."""
        # Act
        response = client.get("/api/voices?lang=it")
        data = response.get_json()

        # Assert
        labels = {s["id"]: s["label"] for s in data["styles"]}
        assert labels["neutro"] == "Neutro"
        assert labels["audiolibro"] == "Audiolibro"

    def test_voices_stili_in_inglese(self, client):
        """GET /api/voices?lang=en deve restituire stili con label inglesi."""
        # Act
        response = client.get("/api/voices?lang=en")
        data = response.get_json()

        # Assert
        labels = {s["id"]: s["label"] for s in data["styles"]}
        assert labels["neutro"] == "Neutral"
        assert labels["audiolibro"] == "Audiobook"

    def test_load_errore_in_italiano(self, client):
        """POST /api/load?lang=it senza file deve restituire errore in italiano."""
        # Act
        response = client.post("/api/load?lang=it", data={})

        # Assert
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Nessun file inviato"

    def test_load_errore_in_inglese(self, client):
        """POST /api/load?lang=en senza file deve restituire errore in inglese."""
        # Act
        response = client.post("/api/load?lang=en", data={})

        # Assert
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "No file provided"

    def test_audio_errore_voce_invalida_en(self, client):
        """GET /api/audio/0?voice=xxx&lang=en deve restituire errore in inglese."""
        # Act
        response = client.get("/api/audio/0?voice=xxx&lang=en")

        # Assert
        assert response.status_code == 400
        data = response.get_json()
        assert "not valid" in data["error"]

    def test_audio_errore_voce_invalida_it(self, client):
        """GET /api/audio/0?voice=xxx&lang=it deve restituire errore in italiano."""
        # Act
        response = client.get("/api/audio/0?voice=xxx&lang=it")

        # Assert
        assert response.status_code == 400
        data = response.get_json()
        assert "non valida" in data["error"]

    def test_save_errore_no_file_en(self, client):
        """POST /api/save?lang=en senza file caricato deve restituire errore in inglese."""
        # Act
        response = client.post(
            "/api/save?lang=en",
            data='{"voice": "giuseppe"}',
            content_type="application/json",
        )

        # Assert
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "No file loaded"

    def test_default_lingua_senza_param(self, client):
        """Senza ?lang=, gli errori devono essere nella lingua di default (italiano)."""
        # Act
        response = client.post("/api/load", data={})

        # Assert
        data = response.get_json()
        assert data["error"] == "Nessun file inviato"
