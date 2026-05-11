## What's Changed in v1.0.0

> First release of AndreaBonn/text-to-speech with support for multiple voices, bilingual UI, and automated setup.

### ✨ New Features
- Add English voices (Andrew, Ava, Ryan) and refactor EDGE_VOICES config (fda0e08)
- Add bilingual IT/EN support across UI and API (6a7c9e4)
- Add automated setup scripts and runtime prerequisite checks (d388c73)
- Add cross-platform audio playback for Linux, macOS, and Windows (34c102a)
- Add reading style presets with SSML prosody control (44a7b16)
- Add multi-format file support and rename leggi_markdown to leggi (a94ab9c)
- Add Flask web interface with TTS engine and audio player (5a6c44e)
- Add markdown reader with Edge TTS and Piper support (7833f43)

### 🐛 Bug Fixes
- Patch 5 known vulnerabilities flagged by pip-audit (22849c1)
- Resolve linting errors from CI (3e3d1e2)
- Remove unused imports flagged by ruff (8109933)
- Replace sleep-based prefetch assertion with synchronous mock (77e4919)
- Resolve race condition in prefetch test and bump Flask to 3.1.3 (cd2832d)
- Add media-src blob: to CSP for audio player (80d0541)
- Apply code roast fixes — async loop, subprocess timeouts, CSP, save POST (61c4ed2)
- Fix concurrency bugs, MP3 concat, Markdown parser, dead JS var (b020c82)
- Harden Flask endpoint against path traversal and info leak (de8fe79)

### 📚 Documentation
- Add web UI screenshots to both EN and IT readmes (ca97a18)
- Update README with complete voice list and reading styles (23471ec)
- Add bilingual README and SECURITY documentation (785cd87)
- Use actual repo URL in git clone (6eb9840)
- Add README and GPL-3.0 license (9822866)

### 🔧 Maintenance
- Reorganize project structure with src/ directory (867876a)
- Extract synthesis.py, fix TOCTOU race condition and regex order (4110390)
- Extract config.py, static files, shared test fixtures (f435061)
- Add AI changelog generator workflow (553bab5)
- Add AI-powered PR review workflow (a3dce59)
- Update badges [skip ci] (d435d41) (87142a1)
- Add dynamic coverage badge to CI and README (4144dc2)
- Update test badge [skip ci] (a151dca)
- Add dynamic test badge and professional README badges (96b8083)
- Add GitHub Actions pipeline and fix Ruff lint errors (6939556)
- Add example output structure, clean up gitignore (7e06184)
- Strengthen assertions to verify behavior, not just non-crash (ee25722)
- Achieve 100% test coverage across all modules (f91828a)
- Add coverage for synthesis, CLI functions, and main entrypoint (94817ac)
- Format leggi.py wrapper with ruff (e47cc52)
- Apply ruff format to test files (0a663ff)
- Add pytest suite for markdown parser, Flask endpoints and TTSEngine (6e0153e)