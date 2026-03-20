"""
app.py
Server Flask per la web UI del TTS reader.

Uso:
    python app.py
    # Apre http://localhost:5000
"""

import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request, Response

from leggi_markdown import EDGE_VOICES, PIPER_VOICES, ALL_VOICES, DEFAULT_VOICE
from tts_engine import TTSEngine

app = Flask(__name__)
engine = TTSEngine()

VOICES_META = [
    {"id": "giuseppe", "label": "Giuseppe", "type": "edge",
     "multilingual": True, "gender": "M"},
    {"id": "isabella", "label": "Isabella", "type": "edge",
     "multilingual": False, "gender": "F"},
    {"id": "elsa", "label": "Elsa", "type": "edge",
     "multilingual": False, "gender": "F"},
    {"id": "diego", "label": "Diego", "type": "edge",
     "multilingual": False, "gender": "M"},
    {"id": "paola", "label": "Paola", "type": "piper",
     "multilingual": False, "gender": "F"},
]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/voices")
def api_voices():
    return jsonify({"voices": VOICES_META, "default": DEFAULT_VOICE})


@app.route("/api/load", methods=["POST"])
def api_load():
    """Carica un file Markdown uploadato e restituisce i paragrafi."""
    if "file" not in request.files:
        return jsonify({"error": "Nessun file inviato"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.endswith(".md"):
        return jsonify({"error": "Serve un file .md"}), 400

    # Salva temporaneamente per pandoc
    with tempfile.NamedTemporaryFile(
        suffix=".md", delete=False, mode="wb"
    ) as tmp:
        file.save(tmp)
        tmp_path = Path(tmp.name)

    try:
        paragraphs = engine.load_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return jsonify({
        "filename": file.filename,
        "total": len(paragraphs),
        "paragraphs": [
            {"idx": i, "text": p, "chars": len(p)}
            for i, p in enumerate(paragraphs)
        ],
    })


@app.route("/api/audio/<int:idx>")
def api_audio(idx):
    """Restituisce l'MP3 sintetizzato per il paragrafo dato."""
    voice = request.args.get("voice", DEFAULT_VOICE)
    if voice not in ALL_VOICES:
        return jsonify({"error": f"Voce '{voice}' non valida"}), 400

    if not engine.paragraphs:
        return jsonify({"error": "Nessun file caricato"}), 400

    try:
        mp3_bytes = engine.get_audio(idx, voice)
    except IndexError:
        return jsonify({"error": f"Paragrafo {idx} non esiste"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return Response(mp3_bytes, mimetype="audio/mpeg")


@app.route("/api/prefetch/<int:idx>")
def api_prefetch(idx):
    """Avvia prefetch del paragrafo in background."""
    voice = request.args.get("voice", DEFAULT_VOICE)
    engine.prefetch(idx, voice)
    return jsonify({"status": "ok"})


@app.route("/api/save")
def api_save():
    """Genera e scarica il file MP3 completo."""
    voice = request.args.get("voice", DEFAULT_VOICE)
    if voice not in ALL_VOICES:
        return jsonify({"error": f"Voce '{voice}' non valida"}), 400
    if not engine.paragraphs:
        return jsonify({"error": "Nessun file caricato"}), 400

    mp3_bytes = engine.save_all(voice)
    safe_name = "".join(
        c for c in engine.filename.replace(".md", ".mp3")
        if c.isalnum() or c in ".-_ "
    )

    return Response(
        mp3_bytes,
        mimetype="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"'
        },
    )


if __name__ == "__main__":
    print("\n  TTS Reader Web UI")
    print("  http://localhost:5000\n")
    app.run(debug=True, port=5000)
