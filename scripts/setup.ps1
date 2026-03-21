# setup.ps1 — Setup automatico TTS Reader per Windows.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"

# ─── Funzioni di output ───────────────────────────────────────────────────

function Write-OK($msg)   { Write-Host "[OK]     $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN]   $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "[ERRORE] $msg" -ForegroundColor Red }

# ─── Verifica Python 3.10+ ────────────────────────────────────────────────

Write-Host ""
Write-OK "Sistema operativo: Windows"

$Python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $result = & $cmd -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
        if ($result -eq "True") {
            $Python = $cmd
            break
        }
    } catch {
        continue
    }
}

if (-not $Python) {
    Write-Fail "Python 3.10+ non trovato."
    Write-Host "         Installa da: https://www.python.org/downloads/"
    Write-Host "         Oppure con:  choco install python  (Chocolatey)"
    Write-Host "                      scoop install python  (Scoop)"
    exit 1
}

$PyVersion = & $Python --version 2>&1
Write-OK "Python: $PyVersion ($Python)"

# ─── Verifica dipendenze di sistema ───────────────────────────────────────

$Errori = 0

# ffmpeg (obbligatorio)
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-OK "ffmpeg: installato"
} else {
    Write-Fail "ffmpeg: NON trovato (obbligatorio)"
    Write-Host "         Installa con: choco install ffmpeg   (Chocolatey)"
    Write-Host "                       scoop install ffmpeg   (Scoop)"
    $Errori++
}

# ffplay (player audio per Windows)
if (Get-Command ffplay -ErrorAction SilentlyContinue) {
    Write-OK "ffplay: installato"
} else {
    Write-Warn "ffplay non trovato. La CLI non potrà riprodurre audio."
    Write-Host "         ffplay è incluso nel pacchetto ffmpeg."
    Write-Host "         Se hai installato ffmpeg, verifica che sia nel PATH."
}

# pandoc (opzionale)
if (Get-Command pandoc -ErrorAction SilentlyContinue) {
    Write-OK "pandoc: installato"
} else {
    Write-Warn "pandoc non trovato (opzionale, migliora la conversione Markdown)"
    Write-Host "         Installa con: choco install pandoc   (Chocolatey)"
    Write-Host "                       scoop install pandoc   (Scoop)"
}

if ($Errori -gt 0) {
    Write-Host ""
    Write-Fail "Installa le dipendenze obbligatorie mancanti e rilancia lo script."
    exit 1
}

# ─── Crea virtual environment ─────────────────────────────────────────────

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$VenvDir = Join-Path $ProjectDir "venv"

Write-Host ""
if (Test-Path $VenvDir) {
    Write-OK "Virtual environment già esistente: venv\"
} else {
    Write-OK "Creo virtual environment..."
    & $Python -m venv $VenvDir
    Write-OK "Virtual environment creato: venv\"
}

# ─── Installa dipendenze Python ───────────────────────────────────────────

$PipPath = Join-Path $VenvDir "Scripts\pip.exe"
$RequirementsPath = Join-Path $ProjectDir "requirements.txt"

Write-OK "Installo dipendenze Python..."
& $PipPath install --upgrade pip --quiet
& $PipPath install -r $RequirementsPath --quiet
Write-OK "Dipendenze Python installate"

# ─── Riepilogo ─────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Setup completato!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Per attivare l'ambiente:"
Write-Host "    venv\Scripts\Activate.ps1       (PowerShell)"
Write-Host "    venv\Scripts\activate.bat       (CMD)"
Write-Host ""
Write-Host "  Per avviare la web UI:"
Write-Host "    python app.py"
Write-Host ""
Write-Host "  Per usare la CLI:"
Write-Host "    python leggi.py file.md"
Write-Host ""
