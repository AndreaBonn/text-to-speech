"""
app.py
Server Flask per la web UI del TTS reader.

Uso:
    python app.py
    # Apre http://localhost:5000
"""

import logging
import os
import re
import tempfile
from pathlib import PurePosixPath, Path
from urllib.parse import quote

from flask import Flask, jsonify, render_template, request, Response

from converters import SUPPORTED_EXTENSIONS
from config import (
    EDGE_VOICES,
    PIPER_VOICES,
    ALL_VOICES,
    DEFAULT_VOICE,
    READING_STYLES,
    ALL_STYLES,
    DEFAULT_STYLE,
    FILE_STYLE_DEFAULTS,
)

from tts_engine import TTSEngine

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB (EPUB/PDF possono essere grandi)

engine = TTSEngine()
log = logging.getLogger(__name__)

# Derivare metadati voci dalla sorgente unica
VOICES_META = [
    {
        "id": vid,
        "label": vid.capitalize(),
        "type": "edge",
        "multilingual": "Multilingual" in edge_id,
        "gender": "M" if vid in ("giuseppe", "diego") else "F",
    }
    for vid, edge_id in EDGE_VOICES.items()
] + [
    {"id": vid, "label": vid.capitalize(), "type": "piper", "multilingual": False, "gender": "F"}
    for vid in sorted(PIPER_VOICES)
]


# ─── Security headers ───────────────────────────────────────────────────────


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "media-src 'self' blob:"
    )
    return response


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File troppo grande (max 50 MB)"}), 413


# ─── Endpoints ───────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/voices")
def api_voices():
    styles_meta = [
        {"id": sid, "label": s["label"], "description": s["description"]}
        for sid, s in READING_STYLES.items()
    ]
    return jsonify(
        {
            "voices": VOICES_META,
            "default": DEFAULT_VOICE,
            "styles": styles_meta,
            "default_style": DEFAULT_STYLE,
        }
    )


def _sanitize_filename(raw_name: str) -> str:
    """Estrae il nome base e rimuove caratteri non sicuri."""
    base = PurePosixPath(raw_name).name
    ext_pattern = "|".join(re.escape(ext) for ext in sorted(SUPPORTED_EXTENSIONS))
    if not re.match(rf"^[\w\-. ]+({ext_pattern})$", base, re.UNICODE):
        return ""
    return base


@app.route("/api/load", methods=["POST"])
def api_load():
    """Carica un file e restituisce i paragrafi."""
    if "file" not in request.files:
        return jsonify({"error": "Nessun file inviato"}), 400

    file = request.files["file"]
    safe_name = _sanitize_filename(file.filename or "")
    if not safe_name:
        validi = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        return jsonify({"error": f"Formato non supportato. Formati validi: {validi}"}), 400

    ext = Path(safe_name).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode="wb") as tmp:
        file.save(tmp)
        tmp_path = Path(tmp.name)

    try:
        paragraphs = engine.load_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    suggested_style = FILE_STYLE_DEFAULTS.get(ext, DEFAULT_STYLE)

    return jsonify(
        {
            "filename": safe_name,
            "total": len(paragraphs),
            "paragraphs": [
                {"idx": i, "text": p, "chars": len(p)} for i, p in enumerate(paragraphs)
            ],
            "suggested_style": suggested_style,
        }
    )


@app.route("/api/audio/<int:idx>")
def api_audio(idx):
    """Restituisce l'MP3 sintetizzato per il paragrafo dato."""
    voice = request.args.get("voice", DEFAULT_VOICE)
    style = request.args.get("style", DEFAULT_STYLE)
    if voice not in ALL_VOICES:
        return jsonify({"error": f"Voce '{voice}' non valida"}), 400
    if style not in ALL_STYLES:
        return jsonify({"error": f"Stile '{style}' non valido"}), 400

    if not engine.paragraphs:
        return jsonify({"error": "Nessun file caricato"}), 400

    try:
        mp3_bytes = engine.get_audio(idx, voice, style)
    except IndexError:
        return jsonify({"error": f"Paragrafo {idx} non esiste"}), 404
    except Exception:
        log.exception("Errore sintesi paragrafo %d con voce %s stile %s", idx, voice, style)
        return jsonify({"error": "Errore durante la sintesi audio"}), 500

    return Response(mp3_bytes, mimetype="audio/mpeg")


@app.route("/api/prefetch/<int:idx>")
def api_prefetch(idx):
    """Avvia prefetch del paragrafo in background."""
    voice = request.args.get("voice", DEFAULT_VOICE)
    style = request.args.get("style", DEFAULT_STYLE)
    engine.prefetch(idx, voice, style)
    return jsonify({"status": "ok"})


@app.route("/api/save", methods=["POST"])
def api_save():
    """Genera e scarica il file MP3 completo."""
    data = request.get_json(silent=True) or {}
    voice = data.get("voice", DEFAULT_VOICE)
    style = data.get("style", DEFAULT_STYLE)
    if voice not in ALL_VOICES:
        return jsonify({"error": f"Voce '{voice}' non valida"}), 400
    if style not in ALL_STYLES:
        return jsonify({"error": f"Stile '{style}' non valido"}), 400
    if not engine.paragraphs:
        return jsonify({"error": "Nessun file caricato"}), 400

    mp3_bytes = engine.save_all(voice, style)

    stem = Path(engine.filename).stem
    safe_name = "".join(c for c in f"{stem}.mp3" if c.isalnum() or c in ".-_ ") or "output.mp3"
    encoded_name = quote(safe_name)

    return Response(
        mp3_bytes,
        mimetype="audio/mpeg",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_name}"; ' f"filename*=UTF-8''{encoded_name}"
            )
        },
    )


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print("\n  TTS Reader Web UI")
    print("  http://localhost:5000\n")
    app.run(debug=debug, port=5000)
