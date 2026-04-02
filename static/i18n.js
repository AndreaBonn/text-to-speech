'use strict';

/* ============================================================
   I18N — Sistema di internazionalizzazione frontend
   Supporta: italiano (it), inglese (en)
============================================================ */

const I18N_TRANSLATIONS = {
  it: {
    /* Toolbar */
    'toolbar.chooseFile':       'Scegli file',
    'toolbar.chooseFileAria':   'Scegli file da leggere',
    'toolbar.voice':            'Voce',
    'toolbar.style':            'Stile',
    'toolbar.voiceAria':        'Selezione voce',
    'toolbar.styleAria':        'Stile di lettura',
    'toolbar.loading':          'Caricamento...',
    'toolbar.saveBtn':          'Salva MP3',
    'toolbar.saveAria':         'Scarica audio completo',
    'toolbar.saveTitle':        'Scarica l\'intero testo come MP3',

    /* Empty state */
    'empty.title':              'Carica un file per iniziare',
    'empty.formats':            'MD, TXT, EPUB, DOCX, HTML, PDF',

    /* Error banner */
    'error.closeAria':          'Chiudi messaggio di errore',

    /* Progress */
    'progress.aria':            'Avanzamento lettura',
    'progress.sliderTitle':     'Clicca per saltare a un punto del testo',
    'progress.counter':         'Paragrafo {current} / {total}',
    'progress.counterEmpty':    'Paragrafo \u2014 / \u2014',
    'progress.valueText':       'Paragrafo {current} di {total}',

    /* Player controls */
    'player.controlsAria':      'Controlli riproduzione',
    'player.startAria':         'Torna all\'inizio',
    'player.startTitle':        'Vai al primo paragrafo',
    'player.prevAria':          'Paragrafo precedente',
    'player.prevTitle':         'Paragrafo precedente (freccia sinistra)',
    'player.playAria':          'Riproduci',
    'player.pauseAria':         'Pausa',
    'player.playTitle':         'Riproduci / Pausa (Spazio)',
    'player.loadingAria':       'Caricamento audio...',
    'player.stopAria':          'Stop',
    'player.stopTitle':         'Stop e torna al primo paragrafo',
    'player.nextAria':          'Paragrafo successivo',
    'player.nextTitle':         'Paragrafo successivo (freccia destra)',
    'player.repeatAria':        'Ripeti paragrafo',
    'player.repeatTitle':       'Ripeti paragrafo corrente (R)',

    /* Control labels */
    'label.start':              'Inizio',
    'label.prev':               'Prec.',
    'label.playPause':          'Play / Pausa',
    'label.stop':               'Stop',
    'label.next':               'Succ.',
    'label.repeat':             'Ripeti',

    /* Keyboard hints */
    'kbd.space':                'Spazio',
    'kbd.playPause':            'Play/Pausa',
    'kbd.prev':                 'Precedente',
    'kbd.next':                 'Successivo',
    'kbd.repeat':               'Ripeti',
    'kbd.aria':                 'Scorciatoie da tastiera disponibili',

    /* Dynamic messages (player.js) */
    'msg.loadError':            'Errore nel caricamento del file.',
    'msg.loadErrorDetail':      'Errore nel caricamento: {message}',
    'msg.synthesisError':       'Errore sintesi audio.',
    'msg.synthesisErrorDetail': 'Errore sintesi: {message} Riprova o cambia voce.',
    'msg.playbackError':        'Errore di riproduzione audio. Riprova o cambia voce.',
    'msg.saveFailed':           'Salvataggio fallito: {message}',
  },

  en: {
    /* Toolbar */
    'toolbar.chooseFile':       'Choose file',
    'toolbar.chooseFileAria':   'Choose a file to read',
    'toolbar.voice':            'Voice',
    'toolbar.style':            'Style',
    'toolbar.voiceAria':        'Voice selection',
    'toolbar.styleAria':        'Reading style',
    'toolbar.loading':          'Loading...',
    'toolbar.saveBtn':          'Save MP3',
    'toolbar.saveAria':         'Download full audio',
    'toolbar.saveTitle':        'Download the entire text as MP3',

    /* Empty state */
    'empty.title':              'Load a file to start',
    'empty.formats':            'MD, TXT, EPUB, DOCX, HTML, PDF',

    /* Error banner */
    'error.closeAria':          'Close error message',

    /* Progress */
    'progress.aria':            'Reading progress',
    'progress.sliderTitle':     'Click to jump to a point in the text',
    'progress.counter':         'Paragraph {current} / {total}',
    'progress.counterEmpty':    'Paragraph \u2014 / \u2014',
    'progress.valueText':       'Paragraph {current} of {total}',

    /* Player controls */
    'player.controlsAria':      'Playback controls',
    'player.startAria':         'Go to beginning',
    'player.startTitle':        'Go to first paragraph',
    'player.prevAria':          'Previous paragraph',
    'player.prevTitle':         'Previous paragraph (left arrow)',
    'player.playAria':          'Play',
    'player.pauseAria':         'Pause',
    'player.playTitle':         'Play / Pause (Space)',
    'player.loadingAria':       'Loading audio...',
    'player.stopAria':          'Stop',
    'player.stopTitle':         'Stop and go to first paragraph',
    'player.nextAria':          'Next paragraph',
    'player.nextTitle':         'Next paragraph (right arrow)',
    'player.repeatAria':        'Repeat paragraph',
    'player.repeatTitle':       'Repeat current paragraph (R)',

    /* Control labels */
    'label.start':              'Start',
    'label.prev':               'Prev',
    'label.playPause':          'Play / Pause',
    'label.stop':               'Stop',
    'label.next':               'Next',
    'label.repeat':             'Repeat',

    /* Keyboard hints */
    'kbd.space':                'Space',
    'kbd.playPause':            'Play/Pause',
    'kbd.prev':                 'Previous',
    'kbd.next':                 'Next',
    'kbd.repeat':               'Repeat',
    'kbd.aria':                 'Available keyboard shortcuts',

    /* Dynamic messages (player.js) */
    'msg.loadError':            'Error loading file.',
    'msg.loadErrorDetail':      'Error loading: {message}',
    'msg.synthesisError':       'Audio synthesis error.',
    'msg.synthesisErrorDetail': 'Synthesis error: {message} Try again or change voice.',
    'msg.playbackError':        'Audio playback error. Try again or change voice.',
    'msg.saveFailed':           'Save failed: {message}',
  },
};

/* ── Stato corrente ─────────────────────────────────────── */

const I18N_DEFAULT_LANG = 'it';
const I18N_STORAGE_KEY  = 'tts-reader-lang';

let _currentLang = localStorage.getItem(I18N_STORAGE_KEY) || I18N_DEFAULT_LANG;

/* ── API pubblica ───────────────────────────────────────── */

/**
 * Restituisce la traduzione per la chiave data, con interpolazione.
 * Esempio: t('progress.counter', {current: 3, total: 10})
 */
function t(key, params) {
  const dict = I18N_TRANSLATIONS[_currentLang] || I18N_TRANSLATIONS[I18N_DEFAULT_LANG];
  let text = dict[key];
  if (text === undefined) {
    /* Fallback alla lingua di default */
    text = I18N_TRANSLATIONS[I18N_DEFAULT_LANG][key] || key;
  }
  if (params) {
    Object.keys(params).forEach(k => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), params[k]);
    });
  }
  return text;
}

/** Restituisce la lingua corrente ('it' o 'en'). */
function i18nGetLang() {
  return _currentLang;
}

/** Cambia lingua e aggiorna tutto il DOM. */
function i18nSetLang(lang) {
  if (!I18N_TRANSLATIONS[lang]) return;
  _currentLang = lang;
  localStorage.setItem(I18N_STORAGE_KEY, lang);
  document.documentElement.lang = lang;
  _applyTranslations();
  _updateLangButtons();
}

/* ── Applicazione al DOM ────────────────────────────────── */

/**
 * Scansiona tutti gli elementi con attributi data-i18n e li aggiorna.
 *
 * data-i18n="key"                → imposta textContent
 * data-i18n-aria-label="key"     → imposta aria-label
 * data-i18n-title="key"          → imposta title
 * data-i18n-placeholder="key"    → imposta placeholder
 */
function _applyTranslations() {
  /* Testo contenuto */
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });

  /* Attributi */
  const attrs = ['aria-label', 'title', 'placeholder'];
  attrs.forEach(attr => {
    const dataAttr = `data-i18n-${attr}`;
    document.querySelectorAll(`[${dataAttr}]`).forEach(el => {
      el.setAttribute(attr, t(el.getAttribute(dataAttr)));
    });
  });
}

/** Aggiorna lo stato visivo dei bottoni lingua. */
function _updateLangButtons() {
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('lang-btn--active', btn.dataset.lang === _currentLang);
    btn.setAttribute('aria-pressed', btn.dataset.lang === _currentLang);
  });
}

/* ── Inizializzazione ───────────────────────────────────── */

function i18nInit() {
  document.documentElement.lang = _currentLang;

  /* Bind bottoni lingua */
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      i18nSetLang(btn.dataset.lang);
      /* Notifica il player che la lingua è cambiata */
      document.dispatchEvent(new CustomEvent('i18n:changed', { detail: { lang: _currentLang } }));
    });
  });

  _applyTranslations();
  _updateLangButtons();
}
