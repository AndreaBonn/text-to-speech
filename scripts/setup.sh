#!/usr/bin/env bash
# setup.sh — Setup automatico TTS Reader per Linux e macOS.
# Uso: bash scripts/setup.sh

set -euo pipefail

# ─── Colori ────────────────────────────────────────────────────────────────

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

info()  { echo -e "${GREEN}[OK]${NC}     $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}   $1"; }
fail()  { echo -e "${RED}[ERRORE]${NC} $1"; }

# ─── Rileva OS ─────────────────────────────────────────────────────────────

OS="$(uname -s)"
case "$OS" in
    Linux*)  PLATFORM="linux";;
    Darwin*) PLATFORM="macos";;
    *)       fail "Sistema operativo non supportato: $OS"; exit 1;;
esac
info "Sistema operativo: $PLATFORM"

# ─── Verifica Python 3.10+ ────────────────────────────────────────────────

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" > /dev/null 2>&1; then
        if "$cmd" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.10+ non trovato."
    if [ "$PLATFORM" = "macos" ]; then
        echo "         Installa con: brew install python@3.12"
    else
        echo "         Installa con: sudo apt install python3  (Debian/Ubuntu)"
        echo "                       sudo dnf install python3  (Fedora)"
        echo "                       sudo pacman -S python     (Arch)"
    fi
    exit 1
fi

PY_VERSION="$($PYTHON --version 2>&1)"
info "Python: $PY_VERSION ($PYTHON)"

# ─── Verifica dipendenze di sistema ───────────────────────────────────────

ERRORI=0

# ffmpeg (obbligatorio)
if command -v ffmpeg > /dev/null 2>&1; then
    info "ffmpeg: installato"
else
    fail "ffmpeg: NON trovato (obbligatorio)"
    if [ "$PLATFORM" = "macos" ]; then
        echo "         Installa con: brew install ffmpeg"
    else
        echo "         Installa con: sudo apt install ffmpeg  (Debian/Ubuntu)"
        echo "                       sudo dnf install ffmpeg  (Fedora)"
        echo "                       sudo pacman -S ffmpeg    (Arch)"
    fi
    ERRORI=$((ERRORI + 1))
fi

# Player audio nativo (opzionale — ffplay è il fallback)
if [ "$PLATFORM" = "linux" ]; then
    if command -v aplay > /dev/null 2>&1; then
        info "aplay: installato"
    elif command -v ffplay > /dev/null 2>&1; then
        warn "aplay non trovato, ma ffplay è disponibile come fallback"
    else
        warn "aplay non trovato. La CLI non potrà riprodurre audio."
        echo "         Installa con: sudo apt install alsa-utils  (Debian/Ubuntu)"
    fi
elif [ "$PLATFORM" = "macos" ]; then
    if command -v afplay > /dev/null 2>&1; then
        info "afplay: installato (nativo macOS)"
    else
        warn "afplay non trovato (dovrebbe essere preinstallato su macOS)"
    fi
fi

# pandoc (opzionale)
if command -v pandoc > /dev/null 2>&1; then
    info "pandoc: installato"
else
    warn "pandoc non trovato (opzionale, migliora la conversione Markdown)"
    if [ "$PLATFORM" = "macos" ]; then
        echo "         Installa con: brew install pandoc"
    else
        echo "         Installa con: sudo apt install pandoc  (Debian/Ubuntu)"
    fi
fi

if [ "$ERRORI" -gt 0 ]; then
    echo ""
    fail "Installa le dipendenze obbligatorie mancanti e rilancia lo script."
    exit 1
fi

# ─── Crea virtual environment ─────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

echo ""
if [ -d "$VENV_DIR" ]; then
    info "Virtual environment già esistente: venv/"
else
    info "Creo virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR"
    info "Virtual environment creato: venv/"
fi

# ─── Installa dipendenze Python ───────────────────────────────────────────

info "Installo dipendenze Python..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt" --quiet
info "Dipendenze Python installate"

# ─── Riepilogo ─────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup completato!${NC}"
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo ""
echo "  Per attivare l'ambiente:"
echo "    source venv/bin/activate"
echo ""
echo "  Per avviare la web UI:"
echo "    python app.py"
echo ""
echo "  Per usare la CLI:"
echo "    python leggi.py file.md"
echo ""
