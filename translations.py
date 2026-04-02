"""
translations.py
Traduzioni backend per messaggi API e label degli stili di lettura.
"""

TRANSLATIONS = {
    "it": {
        "error.file_too_large": "File troppo grande (max 50 MB)",
        "error.no_file": "Nessun file inviato",
        "error.unsupported_format": "Formato non supportato. Formati validi: {formats}",
        "error.invalid_voice": "Voce '{voice}' non valida",
        "error.invalid_style": "Stile '{style}' non valido",
        "error.no_file_loaded": "Nessun file caricato",
        "error.paragraph_not_found": "Paragrafo {idx} non esiste",
        "error.synthesis_failed": "Errore durante la sintesi audio",
        "styles": {
            "neutro": {
                "label": "Neutro",
                "description": "Lettura standard, bilanciata",
            },
            "notiziario": {
                "label": "Notiziario",
                "description": "Ritmo sostenuto e tono energico, come uno speaker",
            },
            "audiolibro": {
                "label": "Audiolibro",
                "description": "Ritmo rilassato e tono caldo, come un narratore",
            },
            "lento": {
                "label": "Lento",
                "description": "Ritmo molto lento, per studio o comprensione",
            },
        },
    },
    "en": {
        "error.file_too_large": "File too large (max 50 MB)",
        "error.no_file": "No file provided",
        "error.unsupported_format": "Unsupported format. Valid formats: {formats}",
        "error.invalid_voice": "Voice '{voice}' is not valid",
        "error.invalid_style": "Style '{style}' is not valid",
        "error.no_file_loaded": "No file loaded",
        "error.paragraph_not_found": "Paragraph {idx} does not exist",
        "error.synthesis_failed": "Audio synthesis error",
        "styles": {
            "neutro": {
                "label": "Neutral",
                "description": "Standard, balanced reading",
            },
            "notiziario": {
                "label": "Newscast",
                "description": "Fast pace and energetic tone, like a news anchor",
            },
            "audiolibro": {
                "label": "Audiobook",
                "description": "Relaxed pace and warm tone, like a narrator",
            },
            "lento": {
                "label": "Slow",
                "description": "Very slow pace, for study or comprehension",
            },
        },
    },
}

DEFAULT_LANG = "it"
SUPPORTED_LANGS = frozenset(TRANSLATIONS.keys())


def get_lang(request) -> str:
    """Determina la lingua dalla richiesta HTTP.

    Cerca in ordine: query param ?lang=, header Accept-Language.
    """
    lang = request.args.get("lang", "").lower()
    if lang in SUPPORTED_LANGS:
        return lang

    accept = request.headers.get("Accept-Language", "")
    for part in accept.split(","):
        code = part.split(";")[0].strip().lower()
        if code[:2] in SUPPORTED_LANGS:
            return code[:2]

    return DEFAULT_LANG


def tr(lang: str, key: str, **kwargs) -> str:
    """Restituisce la traduzione per lingua e chiave, con interpolazione."""
    msgs = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG])
    text = msgs.get(key, TRANSLATIONS[DEFAULT_LANG].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text


def get_styles_meta(lang: str) -> list[dict]:
    """Restituisce i metadati degli stili nella lingua richiesta."""
    from config import READING_STYLES

    styles_i18n = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG])["styles"]
    return [
        {
            "id": sid,
            "label": styles_i18n[sid]["label"],
            "description": styles_i18n[sid]["description"],
        }
        for sid in READING_STYLES
    ]
