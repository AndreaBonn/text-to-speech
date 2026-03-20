# Leggi Markdown

Tool per leggere ad alta voce file Markdown in italiano, con interfaccia web
e da linea di comando. Supporta 5 voci neurali italiane. La voce predefinita
(Giuseppe) è multilingue e pronuncia correttamente anche i termini inglesi
nel testo italiano.

## Funzionalità

- Lettura ad alta voce di file Markdown, paragrafo per paragrafo
- 5 voci italiane: 4 online (Edge TTS) + 1 offline (Piper TTS)
- Interfaccia web con player audio (play, pausa, stop, precedente, successivo, ripeti)
- Interfaccia CLI per uso da terminale
- Salvataggio audio in MP3 (file unico + singoli paragrafi)
- Prefetch intelligente: sintetizza il paragrafo successivo durante la riproduzione
- Conversione automatica Markdown in testo pulito (via pandoc o regex fallback)

## Requisiti di sistema

- Python 3.10+
- ffmpeg (conversione e riproduzione audio)
- aplay (riproduzione CLI, incluso in `alsa-utils` su Linux)
- pandoc (opzionale, migliora la conversione Markdown)

## Installazione

### Dipendenze di sistema (Ubuntu/Debian)

```bash
sudo apt install ffmpeg alsa-utils pandoc
```

### Progetto

```bash
git clone <url-repo>
cd text-to-speech
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Uso

### Interfaccia web

```bash
source venv/bin/activate
python app.py
```

Apri **http://localhost:5000** nel browser. L'interfaccia permette di:

- Caricare un file `.md` dal disco
- Scegliere la voce dal menu a tendina
- Usare i controlli player: play/pausa, stop, precedente, successivo, ripeti
- Cliccare sulla barra di progresso per saltare a qualsiasi paragrafo
- Scaricare l'audio completo in MP3

Scorciatoie tastiera: `Spazio` play/pausa, `freccia sinistra/destra` prev/next, `R` ripeti.

### Linea di comando

```bash
source venv/bin/activate

# Lettura con voce predefinita (Giuseppe, multilingue)
python leggi_markdown.py file.md

# Scelta voce
python leggi_markdown.py file.md --voice isabella

# Voce offline (non serve internet)
python leggi_markdown.py file.md --voice paola

# Salvataggio in MP3
python leggi_markdown.py file.md --voice giuseppe --salva output.mp3
```

Con `--salva` vengono creati:
- Il file MP3 unico specificato
- Una cartella `<nome>_paragrafi/` con un MP3 per ogni paragrafo

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
├── leggi_markdown.py   # CLI: lettura da terminale
├── app.py              # Server Flask per interfaccia web
├── tts_engine.py       # Motore TTS con cache e prefetch
├── templates/
│   └── index.html      # Interfaccia web (player audio)
├── requirements.txt    # Dipendenze Python
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

La voce Paola (Piper TTS) è completamente offline e libera da restrizioni
(dataset di addestramento sotto licenza CC0 public domain).
