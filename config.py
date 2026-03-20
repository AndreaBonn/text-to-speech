"""
config.py
Configurazione centralizzata: voci TTS, path modelli, costanti di progetto.
"""

from pathlib import Path

# ─── Directory di progetto ───────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_INPUT = PROJECT_ROOT / "data" / "input"
DATA_OUTPUT = PROJECT_ROOT / "data" / "output"

# ─── Configurazione voci ─────────────────────────────────────────────────────

EDGE_VOICES = {
    "giuseppe": "it-IT-GiuseppeMultilingualNeural",
    "isabella": "it-IT-IsabellaNeural",
    "elsa": "it-IT-ElsaNeural",
    "diego": "it-IT-DiegoNeural",
}

PIPER_VOICES = {"paola"}

VOICE_DIR = Path.home() / "piper-voices"
VOICE_MODEL = VOICE_DIR / "it_IT-paola-medium.onnx"
VOICE_JSON = VOICE_DIR / "it_IT-paola-medium.onnx.json"

VOICE_URLS = {
    VOICE_MODEL: "https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/it_IT-paola-medium.onnx",
    VOICE_JSON: "https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/it_IT-paola-medium.onnx.json",
}

ALL_VOICES = sorted(list(EDGE_VOICES.keys()) + list(PIPER_VOICES))
DEFAULT_VOICE = "giuseppe"

# ─── Colori terminale ────────────────────────────────────────────────────────

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def info(msg):
    print(f"{GREEN}[INFO]{NC}  {msg}", flush=True)


def warn(msg):
    print(f"{YELLOW}[WARN]{NC}  {msg}", flush=True)


def error(msg):
    print(f"{RED}[ERRORE]{NC} {msg}", flush=True)
