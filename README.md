# TTS Reader

Tool per leggere ad alta voce file di testo in italiano, con interfaccia web
e da linea di comando. Supporta Markdown, TXT, EPUB, DOCX, HTML e PDF
con 5 voci neurali italiane. La voce predefinita (Giuseppe) è multilingue
e pronuncia correttamente anche i termini inglesi nel testo italiano.

## Funzionalità

- Lettura ad alta voce di file di testo (Markdown, TXT, EPUB, DOCX, HTML, PDF), paragrafo per paragrafo
- 5 voci italiane: 4 online (Edge TTS) + 1 offline (Piper TTS)
- Interfaccia web con player audio (play, pausa, stop, precedente, successivo, ripeti)
- Interfaccia CLI per uso da terminale
- Salvataggio audio in MP3 (file unico + singoli paragrafi)
- Prefetch intelligente: sintetizza il paragrafo successivo durante la riproduzione
- Conversione automatica Markdown in testo pulito (via pandoc o regex fallback)

## Requisiti di sistema

- Python 3.10+
- ffmpeg (conversione e riproduzione audio)
- pandoc (opzionale, migliora la conversione Markdown)

La CLI rileva automaticamente il sistema operativo e usa il player audio
appropriato: `aplay` su Linux, `afplay` su macOS, `ffplay` su Windows.
Se il player nativo non è disponibile, `ffplay` (incluso in ffmpeg) viene
usato come fallback su tutti i sistemi.

## Installazione

### Dipendenze di sistema

**Linux (Debian/Ubuntu)**
```bash
sudo apt install ffmpeg alsa-utils pandoc
```

**Linux (Fedora)**
```bash
sudo dnf install ffmpeg alsa-utils pandoc
```

**Linux (Arch)**
```bash
sudo pacman -S ffmpeg alsa-utils pandoc
```

**macOS**
```bash
brew install ffmpeg pandoc
```
`afplay` è già incluso in macOS, non serve installarlo.

**Windows**
```powershell
# Con Chocolatey
choco install ffmpeg pandoc

# Oppure con Scoop
scoop install ffmpeg pandoc
```

### Progetto

```bash
git clone https://github.com/AndreaBonn/text-to-speech.git
cd text-to-speech
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows (cmd)
# venv\Scripts\Activate.ps1     # Windows (PowerShell)
pip install -r requirements.txt
```

## Uso

### Interfaccia web

```bash
source venv/bin/activate
python app.py
```

Apri **http://localhost:5000** nel browser. L'interfaccia permette di:

- Caricare un file dal disco (MD, TXT, EPUB, DOCX, HTML, PDF)
- Scegliere la voce dal menu a tendina
- Usare i controlli player: play/pausa, stop, precedente, successivo, ripeti
- Cliccare sulla barra di progresso per saltare a qualsiasi paragrafo
- Scaricare l'audio completo in MP3

Scorciatoie tastiera: `Spazio` play/pausa, `freccia sinistra/destra` prev/next, `R` ripeti.

### Linea di comando

```bash
source venv/bin/activate

# Lettura con voce predefinita (Giuseppe, multilingue)
python leggi.py file.md

# Scelta voce
python leggi.py file.md --voice isabella

# Voce offline (non serve internet)
python leggi.py file.md --voice paola

# Salvataggio in MP3
python leggi.py file.md --voice giuseppe --salva
```

Con `--salva` viene creata la struttura:
```
data/output/<nome_file>/
├── full/<nome_file>.mp3       # Audio completo
└── paragraphs/
    ├── 001.mp3                # Singoli paragrafi
    ├── 002.mp3
    └── ...
```

## Voci disponibili

| Voce | Motore | Genere | Multilingue | Richiede internet |
|------|--------|--------|-------------|-------------------|
| giuseppe | Edge TTS | Maschile | Si (IT/EN) | Si |
| isabella | Edge TTS | Femminile | No | Si |
| elsa | Edge TTS | Femminile | No | Si |
| diego | Edge TTS | Maschile | No | Si |
| paola | Piper TTS | Femminile | No | No (offline) |

La voce **Giuseppe** è consigliata per testi tecnici con termini inglesi.
La voce **Paola** funziona senza connessione internet (il modello viene
scaricato automaticamente al primo utilizzo, circa 60 MB).

## Struttura progetto

```
text-to-speech/
├── app.py              # Server Flask per interfaccia web
├── tts_engine.py       # Motore TTS con cache e prefetch
├── synthesis.py        # Funzioni di sintesi vocale (Piper, Edge)
├── config.py           # Configurazione voci, path modelli, costanti
├── leggi.py            # CLI: lettura da terminale
├── converters.py       # Convertitori formato → testo piano
├── static/
│   ├── style.css       # Design system (Inchiostro e Ambra)
│   └── player.js       # Player audio JavaScript
├── templates/
│   └── index.html      # Interfaccia web (solo markup HTML)
├── tests/
│   ├── conftest.py     # Fixture condivise (client, engine)
│   └── test_*.py       # Test suite (pytest)
├── data/
│   ├── input/          # File sorgente da leggere
│   └── output/         # Audio generato con --salva
├── docs/               # Documentazione e report attività
├── requirements.txt    # Dipendenze Python
├── CLAUDE.md           # Istruzioni per Claude Code
├── LICENSE             # GPL-3.0
└── README.md
```

## Licenza

Questo progetto è rilasciato sotto licenza **GPL-3.0**. Vedi il file
[LICENSE](LICENSE) per i dettagli.

## Avvertenze

Le voci Edge TTS (giuseppe, isabella, elsa, diego) utilizzano un'API non
ufficiale di Microsoft Edge "Read Aloud". Questo servizio non è garantito
e potrebbe cessare di funzionare in qualsiasi momento. Non è autorizzato
per uso commerciale. Per applicazioni commerciali si consiglia
[Azure AI Speech](https://azure.microsoft.com/it-it/products/ai-services/text-to-speech).

**Uso single-user**: l'applicazione web utilizza un'unica istanza del motore TTS
condivisa tra tutte le richieste. Non è progettata per l'uso simultaneo da parte
di più utenti. Se più utenti caricano file contemporaneamente, i dati verranno
sovrascritti.

La voce Paola (Piper TTS) è completamente offline e libera da restrizioni
(dataset di addestramento sotto licenza CC0 public domain).
