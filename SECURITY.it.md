# Sicurezza

> **[Read in English](SECURITY.md)** | [Torna al README](README.it.md)

Questo documento descrive i meccanismi di sicurezza implementati in TTS Reader.
L'applicazione è progettata per **uso locale single-user** e non include
autenticazione, autorizzazione o rate limiting per scelta progettuale.

## Header di Sicurezza HTTP

Tutte le risposte includono header di sicurezza tramite `@app.after_request`
in [`app.py`](app.py):

| Header | Valore | Scopo |
|--------|--------|-------|
| `X-Content-Type-Options` | `nosniff` | Previene il MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Blocca l'embedding in iframe (clickjacking) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limita le informazioni referrer su richieste cross-origin |
| `Content-Security-Policy` | vedi sotto | Restringe le sorgenti di caricamento risorse |

### Content Security Policy

```
default-src 'self';
script-src 'self';
style-src 'self' https://fonts.googleapis.com;
font-src https://fonts.gstatic.com;
media-src 'self' blob:
```

- **Nessuno script inline o `eval()`** — solo script serviti dalla stessa origine
- **Media da `blob:`** — necessario per la riproduzione audio tramite `URL.createObjectURL()`
- **Font da Google Fonts** — unica risorsa esterna consentita

## Validazione Upload File

L'endpoint `/api/load` ([`app.py`](app.py)) applica diversi livelli di
validazione prima di elaborare qualsiasi file caricato:

**Sanitizzazione filename** (`_sanitize_filename`):
- Estrae il basename tramite `PurePosixPath().name` — neutralizza il path traversal
  (`../../../etc/passwd` diventa `passwd`)
- Whitelist regex `^[\w\-. ]+({estensioni})$` — accetta solo caratteri alfanumerici,
  trattini, punti, spazi e le estensioni consentite
- Rifiuta filename con caratteri speciali, doppie estensioni, null byte

**Whitelist estensioni**:
- Solo `.md`, `.txt`, `.epub`, `.docx`, `.html`, `.htm`, `.pdf` sono accettati
- Tutte le altre estensioni restituiscono HTTP 400

**Limite dimensione**:
- `MAX_CONTENT_LENGTH = 50 MB` — Flask rifiuta upload più grandi con HTTP 413
- Previene esaurimento di memoria e abuso dello spazio disco

## Gestione File Temporanei

I file caricati vengono scritti in file temporanei gestiti dal sistema
operativo con impostazioni sicure:

```python
with tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode="wb") as tmp:
    file.save(tmp)
try:
    paragraphs = engine.load_file(tmp_path)
finally:
    tmp_path.unlink(missing_ok=True)  # pulizia garantita
```

- **Nomi file imprevedibili** — generati dal SO, non derivati dall'input utente
- **Pulizia garantita** — il blocco `finally` assicura l'eliminazione anche in caso di errore
- **Nessuna esposizione in directory pubblica** — i temp file risiedono in `/tmp`, non in static/

La CLI ([`leggi.py`](leggi.py)) applica lo stesso pattern per i file temporanei
di riproduzione.

## Validazione Parametri Input

Tutti gli endpoint API validano i parametri forniti dall'utente tramite
whitelist esplicite prima di eseguire qualsiasi elaborazione:

- **Voce**: deve essere in `ALL_VOICES` (5 valori validi)
- **Stile**: deve essere in `ALL_STYLES` (4 valori validi)
- **Indice paragrafo**: tipizzato come `int` nella route Flask (`/api/audio/<int:idx>`),
  controllo bounds dentro un lock prima dell'accesso all'array

Valori non validi restituiscono HTTP 400 con un messaggio di errore descrittivo.

## Encoding dell'Output

L'endpoint `/api/save` sanitizza il nome del file di download:

```python
safe_name = "".join(c for c in f"{stem}.mp3" if c.isalnum() or c in ".-_ ")
encoded_name = quote(safe_name)
```

- Il filtraggio dei caratteri previene header injection nel `Content-Disposition`
- Encoding RFC 5987 (`filename*=UTF-8''...`) per il supporto Unicode
- `mimetype="audio/mpeg"` esplicito previene confusione MIME

## Thread Safety

Il motore TTS ([`tts_engine.py`](tts_engine.py)) utilizza un `threading.Lock`
per proteggere tutto lo stato mutabile condiviso:

- **Lista paragrafi** — lettura/scrittura sotto lock
- **Cache LRU** — accesso ed eviction sotto lock
- **Caricamento file** — svuota la cache atomicamente quando un nuovo file viene caricato
- **Controllo bounds indice** — eseguito dentro il lock prima di accedere ai paragrafi

Il sistema di prefetch utilizza un `ThreadPoolExecutor` per la sintesi in
background, con tutte le scritture in cache che passano attraverso il metodo
lockato `_put_cache`.

## Sicurezza Lato Client

Il player JavaScript ([`static/player.js`](static/player.js)) segue queste
pratiche:

- **`textContent` al posto di `innerHTML`** — tutto il testo dinamico usa
  `textContent` per prevenire XSS basato su DOM
- **Gestione memoria Blob** — `URL.revokeObjectURL()` viene chiamato su ogni
  blob sostituito per prevenire memory leak
- **Nessun event handler inline** — tutti gli eventi sono collegati programmaticamente

## Sicurezza Download Modelli

Il download del modello vocale Piper ([`synthesis.py`](synthesis.py)):

- Usa **solo HTTPS** (URL HuggingFace hardcodati in [`config.py`](config.py))
- Scarica in chunk da 64 KB — nessuna allocazione dell'intero file in memoria
- Scrive nella home directory dell'utente (`~/piper-voices/`) con i permessi standard del SO

## Cosa NON È Implementato (Per Scelta)

Questi meccanismi sono intenzionalmente assenti perché l'applicazione è
single-user e gira in locale:

| Meccanismo | Motivazione |
|------------|-------------|
| Autenticazione | Single-user, solo localhost |
| Token CSRF | Nessuna sessione autenticata da proteggere |
| Rate limiting | Nessuno scenario di abuso multi-utente |
| CORS | Nessun accesso cross-origin necessario |
| Database | Nessuno storage persistente — tutti i dati sono in memoria |
| HTTPS/TLS | Progettato per localhost; usare un reverse proxy per accesso remoto |

## Segnalazione Vulnerabilità

Se scopri una vulnerabilità di sicurezza, apri una issue su
[GitHub](https://github.com/AndreaBonn/text-to-speech/issues) con
l'etichetta `security`.

## Controlli di Sicurezza in CI

Il progetto esegue audit di sicurezza automatizzati tramite GitHub Actions:

- **[pip-audit](https://github.com/pypa/pip-audit)** — controlla tutte le
  dipendenze Python contro il database OSV (Open Source Vulnerabilities) ad
  ogni push e pull request
- **[Ruff](https://github.com/astral-sh/ruff)** con regole
  [flake8-bandit](https://github.com/tylerwince/flake8-bandit) (prefisso `S`) —
  analisi statica per anti-pattern di sicurezza comuni (password hardcodate,
  `eval` non sicuro, file temporanei insicuri, ecc.)
