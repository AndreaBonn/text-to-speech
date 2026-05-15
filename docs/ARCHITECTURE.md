# Architecture

Technical diagrams for the TTS Reader project. For a high-level overview, see the [README](../README.md).

## System Architecture

Two entry points (Browser and CLI) share the same conversion and synthesis pipeline.

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph LR
    browser["Browser"]
    cli["CLI (leggi.py)"]
    flask["Flask Server"]
    tts_engine["TTSEngine"]
    conv["converters.py"]
    synth["synthesis.py"]
    edge_api["Edge TTS API"]
    piper_model["Piper TTS Model"]
    lru_cache["LRU Cache"]
    cfg["config.py"]

    browser -->|upload file| flask
    browser -->|request audio| flask
    cli -->|read file| conv
    flask -->|parse file| conv
    flask -->|get audio| tts_engine
    tts_engine -->|cache miss| synth
    tts_engine -->|cache hit| lru_cache
    synth -->|online| edge_api
    synth -->|offline| piper_model
    cfg -.->|voices, styles| flask
    cfg -.->|voices, paths| tts_engine

    classDef core fill:#2563eb,stroke:#1d4ed8,color:#fff
    classDef data fill:#d97706,stroke:#b45309,color:#fff
    classDef ext fill:#6b7280,stroke:#4b5563,color:#fff
    classDef engine_cls fill:#059669,stroke:#047857,color:#fff

    class browser,cli core
    class flask,tts_engine engine_cls
    class conv,synth,cfg data
    class edge_api,piper_model ext
    class lru_cache ext
```

**Color legend:** blue = entry points, green = core engine, amber = internal modules, grey = external services/cache.

## Web Playback Sequence

Shows the full request lifecycle: file upload, audio synthesis with LRU cache, and automatic prefetch of the next paragraph via ThreadPoolExecutor.

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Flask
    participant E as TTSEngine
    participant S as synthesis.py
    participant API as Edge TTS API

    B->>F: POST /api/load (file)
    F->>E: load_file(path)
    E->>E: file_a_testo() + split paragraphs
    E-->>F: paragraphs[]
    F-->>B: JSON {paragraphs, suggested_style}

    B->>F: GET /api/audio/0?voice=giuseppe
    F->>E: get_audio(0, giuseppe)
    E->>E: cache miss
    E->>S: sintetizza_edge(voice_id, text)
    S->>API: Edge TTS stream
    API-->>S: MP3 chunks
    S-->>E: MP3 bytes
    E->>E: store in cache
    E->>E: prefetch(1) via ThreadPool
    E-->>F: MP3 bytes
    F-->>B: audio/mpeg

    Note over E,API: Prefetch paragraph N+1 runs in background

    B->>F: GET /api/audio/1
    F->>E: get_audio(1, giuseppe)
    E->>E: cache hit (prefetched)
    E-->>F: MP3 bytes
    F-->>B: audio/mpeg
```

Key details:

- **Cache key format:** `voice:style:index` (e.g. `giuseppe:neutro:0`)
- **Cache eviction:** LRU with max 50 entries (`OrderedDict`)
- **Prefetch:** triggered automatically on every `get_audio()` call for index+1
- **Edge TTS async:** runs on a dedicated `asyncio` event loop in a daemon thread, accessed via `run_coroutine_threadsafe`
- **Piper TTS:** synthesizes WAV, then converts to MP3 via `ffmpeg` pipe

## File Conversion Pipeline

`converters.py` dispatches to format-specific converters. The Markdown path has a graceful degradation: pandoc when available, regex stripping otherwise.

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TD
    input_file["Input File"]
    dispatch["file_a_testo()"]
    md_fmt["Markdown"]
    txt_fmt["Plain Text"]
    epub_fmt["EPUB"]
    docx_fmt["DOCX"]
    html_fmt["HTML"]
    pdf_fmt["PDF"]
    pandoc_tool["pandoc"]
    regex_fb["Regex fallback"]
    bs4_lib["BeautifulSoup"]
    pymupdf_lib["PyMuPDF"]
    docx_lib["python-docx"]
    plain_text["Clean Text"]
    split_step["Split paragraphs"]

    input_file --> dispatch
    dispatch --> md_fmt
    dispatch --> txt_fmt
    dispatch --> epub_fmt
    dispatch --> docx_fmt
    dispatch --> html_fmt
    dispatch --> pdf_fmt

    md_fmt -->|pandoc available| pandoc_tool
    md_fmt -->|no pandoc| regex_fb
    txt_fmt --> plain_text
    epub_fmt --> bs4_lib
    docx_fmt --> docx_lib
    html_fmt --> bs4_lib
    pdf_fmt --> pymupdf_lib

    pandoc_tool --> plain_text
    regex_fb --> plain_text
    bs4_lib --> plain_text
    docx_lib --> plain_text
    pymupdf_lib --> plain_text
    plain_text --> split_step

    classDef core fill:#2563eb,stroke:#1d4ed8,color:#fff
    classDef data fill:#d97706,stroke:#b45309,color:#fff
    classDef ext fill:#6b7280,stroke:#4b5563,color:#fff
    classDef engine_cls fill:#059669,stroke:#047857,color:#fff

    class input_file core
    class dispatch,split_step engine_cls
    class md_fmt,txt_fmt,epub_fmt,docx_fmt,html_fmt,pdf_fmt data
    class pandoc_tool,regex_fb,bs4_lib,pymupdf_lib,docx_lib ext
```

**Color legend:** blue = input, green = dispatch/output, amber = format types, grey = conversion tools.

After conversion, text is split on double newlines (`\n\n`) into paragraphs for sequential synthesis.
