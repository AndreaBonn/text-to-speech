'use strict';

/* ============================================================
   TTSPLAYER — classe principale
============================================================ */
class TtsPlayer {
  constructor() {
    /* Dati */
    this.paragraphs  = [];   // [{idx, text, chars}]
    this.currentIdx  = 0;
    this.totalCount  = 0;
    this.currentVoice = '';
    this.filename    = '';

    /* Stato player */
    this._state      = 'idle'; // 'idle' | 'loading' | 'playing' | 'paused'

    /* Audio element unico */
    this._audio      = new Audio();
    this._audio.preload = 'auto';

    /* Prefetch blob */
    this._currentBlobUrl = null; // ObjectURL audio corrente
    this._prefetchIdx  = -1;     // Indice a cui si riferisce il blob
    this._prefetchUrl  = null;   // ObjectURL attivo

    /* Bind event handler audio */
    this._audio.addEventListener('ended',   () => this._onEnded());
    this._audio.addEventListener('error',   () => this._onAudioError());
    this._audio.addEventListener('playing', () => this._onPlaying());
    this._audio.addEventListener('pause',   () => this._onPaused());

    /* Cache DOM */
    this._dom = {
      emptyState:      document.getElementById('empty-state'),
      paragraphText:   document.getElementById('paragraph-text'),
      readerCard:      document.getElementById('reader-card'),
      progressBar:     document.getElementById('progress-bar'),
      progressFill:    document.getElementById('progress-fill'),
      progressCounter: document.getElementById('progress-counter'),
      btnPlay:         document.getElementById('btn-play'),
      btnStop:         document.getElementById('btn-stop'),
      btnPrev:         document.getElementById('btn-prev'),
      btnNext:         document.getElementById('btn-next'),
      btnStart:        document.getElementById('btn-start'),
      btnRepeat:       document.getElementById('btn-repeat'),
      iconPlay:        document.getElementById('icon-play'),
      iconPause:       document.getElementById('icon-pause'),
      voiceSelect:     document.getElementById('voice-select'),
      fileInput:       document.getElementById('file-input'),
      fileName:        document.getElementById('file-name'),
      btnSave:         document.getElementById('btn-save'),
      errorBanner:     document.getElementById('error-banner'),
      errorMsg:        document.getElementById('error-banner-msg'),
    };

    this._bindUI();
    this._loadVoices();
  }

  /* ----------------------------------------------------------
     INIT: carica voci dal server
  ---------------------------------------------------------- */
  async _loadVoices() {
    try {
      const res  = await fetch('/api/voices');
      const data = await res.json();
      const sel  = this._dom.voiceSelect;
      sel.innerHTML = '';
      data.voices.forEach(v => {
        const opt  = document.createElement('option');
        opt.value  = v.id;
        opt.textContent = v.label + (v.multilingual ? ' (multi)' : '');
        sel.appendChild(opt);
      });
      sel.value         = data.default;
      this.currentVoice = data.default;
      this._updateSaveLink();
    } catch (err) {
      console.error('Errore caricamento voci:', err);
    }
  }

  /* ----------------------------------------------------------
     BIND UI: eventi DOM
  ---------------------------------------------------------- */
  _bindUI() {
    /* File input */
    this._dom.fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      this._dom.fileName.textContent = file.name;
      const fd = new FormData();
      fd.append('file', file);
      this.loadFile(fd);
    });

    /* Voice select */
    this._dom.voiceSelect.addEventListener('change', () => {
      this.currentVoice = this._dom.voiceSelect.value;
      this._updateSaveLink();
      /* Svuota prefetch cache se cambia voce */
      this._clearPrefetch();
    });

    /* Bottoni player */
    this._dom.btnPlay.addEventListener('click', () => {
      if (this._state === 'playing') {
        this.pause();
      } else {
        this.play();
      }
    });

    this._dom.btnStop.addEventListener('click',   () => this.stop());
    this._dom.btnPrev.addEventListener('click',   () => this.prev());
    this._dom.btnNext.addEventListener('click',   () => this.next());
    this._dom.btnStart.addEventListener('click',  () => this.goTo(0));
    this._dom.btnRepeat.addEventListener('click', () => this.repeat());

    /* Save: POST /api/save → download blob MP3 */
    this._dom.btnSave.addEventListener('click', () => this._handleSave());

    /* Progress bar: click per saltare */
    this._dom.progressBar.addEventListener('click', (e) => {
      if (!this.totalCount) return;
      const rect   = this._dom.progressBar.getBoundingClientRect();
      const ratio  = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
      const idx    = Math.round(ratio * (this.totalCount - 1));
      this.goTo(idx);
      if (this._state === 'paused' || this._state === 'idle') {
        this.play();
      }
    });

    /* Progress bar: keyboard (slider ARIA) */
    this._dom.progressBar.addEventListener('keydown', (e) => {
      if (!this.totalCount) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); this.next(); }
      if (e.key === 'ArrowLeft')  { e.preventDefault(); this.prev(); }
      if (e.key === 'Home')       { e.preventDefault(); this.goTo(0); }
      if (e.key === 'End')        { e.preventDefault(); this.goTo(this.totalCount - 1); }
    });

    /* Chiudi banner errore */
    document.getElementById('btn-close-error')
      .addEventListener('click', () => this._hideError());

    /* Scorciatoie tastiera globali */
    document.addEventListener('keydown', (e) => {
      /* Ignora se focus su input/select */
      const tag = document.activeElement.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;

      if (e.code === 'Space') {
        e.preventDefault();
        if (this._state === 'playing') { this.pause(); } else { this.play(); }
      }
      if (e.key === 'ArrowLeft')  { e.preventDefault(); this.prev(); }
      if (e.key === 'ArrowRight') { e.preventDefault(); this.next(); }
      if (e.key === 'r' || e.key === 'R') { this.repeat(); }
    });
  }

  /* ----------------------------------------------------------
     API PUBBLICA
  ---------------------------------------------------------- */

  /** Carica un file .md via FormData POST /api/load */
  async loadFile(formData) {
    this._setState('loading');
    this._setPlayIconLoading(true);

    try {
      const res  = await fetch('/api/load', { method: 'POST', body: formData });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Errore nel caricamento del file.');
      }

      this.paragraphs   = data.paragraphs;
      this.totalCount   = data.total;
      this.filename     = data.filename;
      this.currentIdx   = 0;

      this._clearPrefetch();
      this._setState('idle');
      this._setPlayIconLoading(false);

      /* Aggiorna UI */
      this._dom.emptyState.classList.add('hidden');
      this._dom.paragraphText.classList.remove('hidden');
      this._dom.readerCard.classList.remove('reader-card--empty');
      this._dom.btnSave.classList.remove('hidden');
      this._updateSaveLink();
      this.updateUI();

      /* Abilita controlli */
      this._setControlsEnabled(true);

      /* Avvia prefetch del primo paragrafo (non riproduce) */
      this.prefetchNext(-1);

    } catch (err) {
      this._setState('idle');
      this._setPlayIconLoading(false);
      this._showError('Errore nel caricamento: ' + err.message);
    }
  }

  /** Inizia o riprende la riproduzione */
  async play() {
    if (!this.totalCount) return;
    if (this._state === 'playing') return;

    /* Se in pausa, riprendi semplicemente */
    if (this._state === 'paused' && this._audio.src && !this._audio.ended) {
      this._audio.play().catch(() => this._loadAndPlay(this.currentIdx));
      return;
    }

    await this._loadAndPlay(this.currentIdx);
  }

  /** Mette in pausa */
  pause() {
    if (this._state !== 'playing') return;
    this._audio.pause();
  }

  /** Stop: ferma e torna al paragrafo 0 */
  stop() {
    this._audio.pause();
    this._audio.src = '';
    this.currentIdx = 0;
    this._setState('idle');
    this.updateUI();
  }

  /** Paragrafo successivo */
  async next() {
    if (!this.totalCount) return;
    if (this.currentIdx >= this.totalCount - 1) return;
    const wasPlaying = this._state === 'playing';
    this._audio.pause();
    this.currentIdx++;
    this.updateUI();
    if (wasPlaying) await this._loadAndPlay(this.currentIdx);
  }

  /** Paragrafo precedente */
  async prev() {
    if (!this.totalCount) return;
    if (this.currentIdx <= 0) return;
    const wasPlaying = this._state === 'playing';
    this._audio.pause();
    this.currentIdx--;
    this.updateUI();
    if (wasPlaying) await this._loadAndPlay(this.currentIdx);
  }

  /** Ripete il paragrafo corrente dall'inizio */
  async repeat() {
    if (!this.totalCount) return;
    this._audio.pause();
    this._clearPrefetch();
    await this._loadAndPlay(this.currentIdx);
  }

  /** Salta a un paragrafo specifico */
  async goTo(index) {
    if (!this.totalCount) return;
    const idx = Math.min(Math.max(0, index), this.totalCount - 1);
    const wasPlaying = this._state === 'playing';
    this._audio.pause();
    this.currentIdx = idx;
    this.updateUI();
    if (wasPlaying) await this._loadAndPlay(this.currentIdx);
  }

  /** Prefetch blob del paragrafo N+1 in background (silenzioso) */
  async prefetchNext(currentIdx) {
    const nextIdx = currentIdx + 1;
    if (nextIdx >= this.totalCount) return;
    if (this._prefetchIdx === nextIdx) return; /* gia' in cache */

    try {
      const url = `/api/audio/${nextIdx}?voice=${encodeURIComponent(this.currentVoice)}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const blob = await res.blob();

      /* Revoca il vecchio ObjectURL prima di creare il nuovo */
      this._clearPrefetch();

      this._prefetchIdx  = nextIdx;
      this._prefetchUrl  = URL.createObjectURL(blob);
    } catch (_) {
      /* Prefetch fallito silenziosamente: non blocca il player */
    }
  }

  /** Aggiorna testo, contatore, progress bar e stato bottoni */
  updateUI() {
    const para = this.paragraphs[this.currentIdx];

    /* Testo con fade */
    if (para) {
      const el = this._dom.paragraphText;
      el.classList.add('fade-out');
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.textContent = para.text;
          el.classList.remove('fade-out');
        });
      });
    }

    /* Contatore */
    if (this.totalCount) {
      this._dom.progressCounter.textContent =
        `Paragrafo ${this.currentIdx + 1} / ${this.totalCount}`;
    } else {
      this._dom.progressCounter.textContent = 'Paragrafo — / —';
    }

    /* Progress bar */
    const pct = this.totalCount > 1
      ? (this.currentIdx / (this.totalCount - 1)) * 100
      : 0;
    this._dom.progressFill.style.width = pct.toFixed(2) + '%';
    this._dom.progressBar.setAttribute('aria-valuenow', Math.round(pct));
    this._dom.progressBar.setAttribute('aria-valuetext',
      `Paragrafo ${this.currentIdx + 1} di ${this.totalCount}`);

    /* Stato bottoni prev/next/start */
    this._dom.btnPrev.disabled  = !this.totalCount || this.currentIdx <= 0;
    this._dom.btnStart.disabled = !this.totalCount || this.currentIdx <= 0;
    this._dom.btnNext.disabled  = !this.totalCount || this.currentIdx >= this.totalCount - 1;

    /* Icone play/pause */
    this._updatePlayIcon();
  }

  /* ----------------------------------------------------------
     PRIVATE: load and play
  ---------------------------------------------------------- */
  async _loadAndPlay(idx) {
    this._setState('loading');
    this._setPlayIconLoading(true);

    try {
      let audioSrc;

      /* Usa prefetch blob se disponibile per questo indice */
      if (this._prefetchIdx === idx && this._prefetchUrl) {
        audioSrc = this._prefetchUrl;
      } else {
        /* Fetch diretto */
        const url = `/api/audio/${idx}?voice=${encodeURIComponent(this.currentVoice)}`;
        const res = await fetch(url);

        if (!res.ok) {
          let msg = 'Errore sintesi audio.';
          try { const d = await res.json(); msg = d.error || msg; } catch(_) {}
          throw new Error(msg);
        }

        const blob = await res.blob();

        /* Revoca vecchio url solo se non e' il prefetch che stiamo usando */
        if (this._prefetchUrl && this._prefetchIdx !== idx) {
          this._clearPrefetch();
        }

        audioSrc = URL.createObjectURL(blob);
        /* Salva il riferimento per poterlo revocare dopo */
        this._currentBlobUrl = audioSrc;
      }

      this._audio.src = audioSrc;
      await this._audio.play();

      this._setPlayIconLoading(false);

      /* Avvia prefetch del prossimo in background */
      this.prefetchNext(idx);

    } catch (err) {
      this._setState('idle');
      this._setPlayIconLoading(false);
      this._showError(`Errore sintesi: ${err.message} Riprova o cambia voce.`);
    }
  }

  /* ----------------------------------------------------------
     PRIVATE: event handlers audio element
  ---------------------------------------------------------- */
  _onEnded() {
    /* Revoca l'url del blob corrente se non e' il prefetch */
    if (this._currentBlobUrl && this._currentBlobUrl !== this._prefetchUrl) {
      URL.revokeObjectURL(this._currentBlobUrl);
      this._currentBlobUrl = null;
    }

    /* Avanzamento automatico */
    if (this.currentIdx < this.totalCount - 1) {
      this.currentIdx++;
      this.updateUI();
      this._loadAndPlay(this.currentIdx);
    } else {
      /* Fine testo */
      this._setState('idle');
      this.updateUI();
    }
  }

  _onPlaying() {
    this._setState('playing');
    this._setPlayIconLoading(false);
    this.updateUI();
  }

  _onPaused() {
    if (this._state !== 'idle') {
      this._setState('paused');
      this.updateUI();
    }
  }

  _onAudioError() {
    if (this._state === 'loading' || this._state === 'playing') {
      this._setState('idle');
      this._setPlayIconLoading(false);
      this._showError('Errore di riproduzione audio. Riprova o cambia voce.');
      this.updateUI();
    }
  }

  /* ----------------------------------------------------------
     PRIVATE: stato player
  ---------------------------------------------------------- */
  _setState(state) {
    this._state = state;
    /* Abilita/disabilita bottone stop e play in base allo stato */
    const hasFile = this.totalCount > 0;
    this._dom.btnPlay.disabled   = !hasFile || state === 'loading';
    this._dom.btnStop.disabled   = !hasFile || (state === 'idle');
    this._dom.btnRepeat.disabled = !hasFile;
  }

  _setControlsEnabled(enabled) {
    [
      this._dom.btnPlay,
      this._dom.btnStop,
      this._dom.btnPrev,
      this._dom.btnNext,
      this._dom.btnStart,
      this._dom.btnRepeat,
    ].forEach(btn => { btn.disabled = !enabled; });

    if (enabled) {
      /* Ridefinisci correttamente lo stato iniziale */
      this._setState('idle');
      this.updateUI();
    }
  }

  /* ----------------------------------------------------------
     PRIVATE: icone play button
  ---------------------------------------------------------- */
  _updatePlayIcon() {
    const isPlaying = this._state === 'playing';
    const isLoading = this._state === 'loading';

    if (!isLoading) {
      this._dom.iconPlay.classList.toggle('hidden', isPlaying);
      this._dom.iconPause.classList.toggle('hidden', !isPlaying);
      this._dom.btnPlay.classList.remove('is-loading');
    }

    this._dom.btnPlay.setAttribute('aria-label',
      isPlaying ? 'Pausa' : 'Riproduci');
  }

  _setPlayIconLoading(loading) {
    if (loading) {
      this._dom.btnPlay.classList.add('is-loading');
      this._dom.iconPlay.classList.add('hidden');
      this._dom.iconPause.classList.add('hidden');
      this._dom.btnPlay.setAttribute('aria-label', 'Caricamento audio...');
    } else {
      this._dom.btnPlay.classList.remove('is-loading');
      this._updatePlayIcon();
    }
  }

  /* ----------------------------------------------------------
     PRIVATE: prefetch cache
  ---------------------------------------------------------- */
  _clearPrefetch() {
    if (this._prefetchUrl) {
      URL.revokeObjectURL(this._prefetchUrl);
    }
    this._prefetchUrl  = null;
    this._prefetchIdx  = -1;
  }

  /* ----------------------------------------------------------
     PRIVATE: save (POST /api/save → download blob)
  ---------------------------------------------------------- */
  _updateSaveLink() {
    this._dom.btnSave.dataset.voice = this.currentVoice;
  }

  async _handleSave() {
    const voice = this._dom.btnSave.dataset.voice;
    if (!voice) return;

    const btn = this._dom.btnSave;
    btn.disabled = true;

    try {
      const res = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `Errore ${res.status}`);
      }

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `tts_${voice}.mp3`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

    } catch (err) {
      this._showError(`Salvataggio fallito: ${err.message}`);
    } finally {
      btn.disabled = false;
    }
  }

  /* ----------------------------------------------------------
     PRIVATE: errori
  ---------------------------------------------------------- */
  _showError(msg) {
    this._dom.errorMsg.textContent = msg;
    this._dom.errorBanner.classList.remove('hidden');

    /* Auto-dismiss dopo 5 secondi */
    clearTimeout(this._errorTimer);
    this._errorTimer = setTimeout(() => this._hideError(), 5000);
  }

  _hideError() {
    this._dom.errorBanner.classList.add('hidden');
    clearTimeout(this._errorTimer);
  }
}

/* ============================================================
   BOOTSTRAP
============================================================ */
const player = new TtsPlayer();
