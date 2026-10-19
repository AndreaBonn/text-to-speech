'use strict';

/* ============================================================
   I18N — Sistema di internazionalizzazione frontend
   Supporta: italiano (it), inglese (en)
============================================================ */

const I18N_TRANSLATIONS = {
  it: {
    /* Toolbar */
    'app.title':                'Lettore ad alta voce',
    'toolbar.lang':             'Lingua dei menu',
    'toolbar.langAria':         'Lingua dei menu (non cambia la voce)',
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
    'empty.drop':               'Trascina qui un documento, oppure',
    'empty.choose':             'Scegli un file dal computer',
    'empty.formats':            'Documenti Word e PDF, libri EPUB, pagine web, file di testo',
    'steps.aria':               'Come si usa',
    'reader.clickHint':         'Clicca un paragrafo per ascoltarlo da lì',
    'doc.paragraphs':           '{n} paragrafi',
    'doc.oneParagraph':         '1 paragrafo',
    'doc.meta':                 '{count} · {duration} di ascolto',
    'duration.underMinute':     'meno di un minuto',
    'duration.oneMinute':       'circa 1 minuto',
    'duration.minutes':         'circa {n} minuti',
    'duration.hours':           'circa {h} h e {m} min',
    'empty.paste':              'oppure incolla un testo',
    'empty.sample':             'prova con un testo di esempio',
    'paste.label':              'Testo da ascoltare',
    'paste.placeholder':        'Incolla qui una mail, un articolo, un appunto...',
    'paste.go':                 'Ascolta questo testo',
    'sample.text':              'Questo è un testo di prova, per sentire come suona la voce scelta.\n\nPuoi cambiare voce e stile dal menu in alto, anche mentre ascolti.\n\nQuando sei pronto, carica un tuo documento: Word, PDF, un libro EPUB o una pagina web.',
    'steps.load':               'Carica il testo',
    'steps.voice':              'Scegli la voce',
    'steps.listen':             'Premi Ascolta',
    'player.idle':              'I comandi per ascoltare compaiono qui appena carichi un testo.',

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
    'player.playAria':          'Ascolta',
    'player.pauseAria':         'Pausa',
    'player.playTitle':         'Ascolta / Pausa (Spazio)',
    'player.loadingAria':       'Caricamento audio...',
    'player.stopAria':          'Stop',
    'player.stopTitle':         'Stop e torna al primo paragrafo',
    'player.nextAria':          'Paragrafo successivo',
    'player.nextTitle':         'Paragrafo successivo (freccia destra)',
    'player.repeatAria':        'Riascolta il paragrafo',
    'player.repeatTitle':       'Riascolta il paragrafo dall\'inizio (R)',

    /* Control labels */
    'label.start':              'Dall\'inizio',
    'label.prev':               'Indietro',
    'label.listen':             'Ascolta',
    'label.pause':              'Pausa',
    'label.stop':               'Stop',
    'label.next':               'Avanti',
    'label.repeat':             'Riascolta',

    /* Keyboard hints */
    'kbd.space':                'Spazio',
    'kbd.playPause':            'Ascolta/Pausa',
    'kbd.prev':                 'Indietro',
    'kbd.next':                 'Avanti',
    'kbd.repeat':               'Riascolta',
    'kbd.aria':                 'Scorciatoie da tastiera disponibili',

    /* Dynamic messages (player.js) */
    'msg.loadError':            'Non sono riuscito a caricare il file. Riprova.',
    'msg.network':              'Non riesco a contattare il lettore: controlla che il programma sia ancora aperto e riprova.',
    'msg.synthesisError':       'Non sono riuscito a preparare l\'audio. Riprova o scegli un\'altra voce.',
    'msg.playbackError':        'Il browser non è riuscito a riprodurre l\'audio. Riprova o scegli un\'altra voce.',
    'msg.saveFailed':           'Non sono riuscito a creare l\'MP3. Riprova.',
    'action.listenWith':        'Ascolta con {voice} (senza internet)',
    'action.saveWith':          'Salva con {voice} (senza internet)',
  },

  en: {
    /* Toolbar */
    'app.title':                'Read Aloud',
    'toolbar.lang':             'Menu language',
    'toolbar.langAria':         'Menu language (does not change the voice)',
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
    'empty.drop':               'Drop a document here, or',
    'empty.choose':             'Choose a file from your computer',
    'empty.formats':            'Word and PDF documents, EPUB books, web pages, text files',
    'steps.aria':               'How it works',
    'reader.clickHint':         'Click a paragraph to listen from there',
    'doc.paragraphs':           '{n} paragraphs',
    'doc.oneParagraph':         '1 paragraph',
    'doc.meta':                 '{count} · {duration} of listening',
    'duration.underMinute':     'under a minute',
    'duration.oneMinute':       'about 1 minute',
    'duration.minutes':         'about {n} minutes',
    'duration.hours':           'about {h} h {m} min',
    'empty.paste':              'or paste a text',
    'empty.sample':             'try a sample text',
    'paste.label':              'Text to listen to',
    'paste.placeholder':        'Paste an email, an article, a note...',
    'paste.go':                 'Listen to this text',
    'sample.text':              'This is a sample text, to hear how the chosen voice sounds.\n\nYou can change voice and style from the menu at the top, even while listening.\n\nWhen you are ready, load one of your documents: Word, PDF, an EPUB book or a web page.',
    'steps.load':               'Load the text',
    'steps.voice':              'Choose the voice',
    'steps.listen':             'Press Listen',
    'player.idle':              'The listening controls appear here as soon as you load a text.',

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
    'player.playAria':          'Listen',
    'player.pauseAria':         'Pause',
    'player.playTitle':         'Listen / Pause (Space)',
    'player.loadingAria':       'Loading audio...',
    'player.stopAria':          'Stop',
    'player.stopTitle':         'Stop and go to first paragraph',
    'player.nextAria':          'Next paragraph',
    'player.nextTitle':         'Next paragraph (right arrow)',
    'player.repeatAria':        'Replay paragraph',
    'player.repeatTitle':       'Replay the paragraph from the start (R)',

    /* Control labels */
    'label.start':              'From start',
    'label.prev':               'Back',
    'label.listen':             'Listen',
    'label.pause':              'Pause',
    'label.stop':               'Stop',
    'label.next':               'Next',
    'label.repeat':             'Replay',

    /* Keyboard hints */
    'kbd.space':                'Space',
    'kbd.playPause':            'Listen/Pause',
    'kbd.prev':                 'Back',
    'kbd.next':                 'Next',
    'kbd.repeat':               'Replay',
    'kbd.aria':                 'Available keyboard shortcuts',

    /* Dynamic messages (player.js) */
    'msg.loadError':            'I couldn\'t load the file. Please try again.',
    'msg.network':              'I can\'t reach the reader: check that the program is still running and try again.',
    'msg.synthesisError':       'I couldn\'t prepare the audio. Try again or choose another voice.',
    'msg.playbackError':        'The browser couldn\'t play the audio. Try again or choose another voice.',
    'msg.saveFailed':           'I couldn\'t create the MP3. Please try again.',
    'action.listenWith':        'Listen with {voice} (no internet needed)',
    'action.saveWith':          'Save with {voice} (no internet needed)',
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
