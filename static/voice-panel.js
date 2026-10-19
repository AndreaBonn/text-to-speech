'use strict';

/* ============================================================
   VOICE PANEL — scelta di voce e stile in un pannello apribile
   Voci divise per lingua e descritte a parole, stili come
   schede con descrizione, preferenze ricordate fra le visite.
============================================================ */
const VOICE_PREF_KEY = 'tts-reader-voice';

/** Gruppo di radio con la stessa interfaccia minima di un <select>. */
class StylePicker {
  constructor(fieldset, list) {
    this._fieldset = fieldset;
    this._list = list;
    this._labels = {};
    this._listeners = [];
    list.addEventListener('change', (e) => {
      if (e.target.name === 'style') this._listeners.forEach(fn => fn());
    });
  }

  setOptions(styles) {
    const frag = document.createDocumentFragment();
    this._labels = {};
    styles.forEach((s) => {
      this._labels[s.id] = s.label;
      const card = document.createElement('label');
      card.className = 'style-card';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'style';
      input.value = s.id;
      const title = document.createElement('span');
      title.className = 'style-card__title';
      title.textContent = s.label;
      const desc = document.createElement('span');
      desc.className = 'style-card__desc';
      desc.textContent = s.description;
      card.append(input, title, desc);
      frag.appendChild(card);
    });
    this._list.replaceChildren(frag);
  }

  get value() {
    const checked = this._list.querySelector('input[name="style"]:checked');
    return checked ? checked.value : '';
  }

  set value(id) {
    const input = this._list.querySelector(`input[name="style"][value="${CSS.escape(id)}"]`);
    if (input) input.checked = true;
  }

  get disabled() { return this._fieldset.disabled; }
  set disabled(flag) { this._fieldset.disabled = flag; }

  labelOf(id) { return this._labels[id] || id; }

  addEventListener(type, fn) {
    if (type === 'change') this._listeners.push(fn);
  }
}

class VoicePanel {
  constructor() {
    const $ = (id) => document.getElementById(id);
    this._dom = {
      toggle: $('btn-voice-panel'), summary: $('voice-summary'), panel: $('voice-panel'),
      done: $('btn-voice-done'), voiceSelect: $('voice-select'), voiceDesc: $('voice-desc'),
      offlineNote: $('voice-offline-note'), styleNote: $('style-offline-note'),
      autoBar: $('auto-style-note'), autoText: $('auto-style-text'), autoChange: $('btn-auto-style'),
    };
    this.styles = new StylePicker($('style-group'), $('style-list'));
    this._voices = {};
    this._online = true;

    this._dom.toggle.addEventListener('click', () => (this.isOpen() ? this.close() : this.open()));
    this._dom.done.addEventListener('click', () => this.close(true));
    this._dom.autoChange.addEventListener('click', () => this.open());
    this._dom.panel.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.close(true);
    });
  }

  isOpen() { return !this._dom.panel.classList.contains('hidden'); }

  open() {
    this._dom.panel.classList.remove('hidden');
    this._dom.toggle.setAttribute('aria-expanded', 'true');
    this._dom.voiceSelect.focus();
  }

  close(returnFocus = false) {
    this._dom.panel.classList.add('hidden');
    this._dom.toggle.setAttribute('aria-expanded', 'false');
    if (returnFocus) this._dom.toggle.focus();
  }

  /**
   * Riempie voci e stili; restituisce {voice, style} da usare.
   * `keep` = scelta già in corso (cambio lingua): ha la precedenza sulla preferenza salvata.
   */
  populate(data, keep = null) {
    this._online = data.online_available !== false;
    this._voices = Object.fromEntries(data.voices.map(v => [v.id, v]));
    this._fillVoices(data.voices);
    this.styles.setOptions(data.styles);

    const pref = keep || loadPref(VOICE_PREF_KEY, {});
    const prefVoice = this._voices[pref.voice];
    const prefUsable = prefVoice && (this._online || prefVoice.type !== 'edge');
    const voice = prefUsable ? pref.voice : data.default;
    const style = pref.style && data.styles.some(s => s.id === pref.style) ? pref.style : data.default_style;
    this._dom.voiceSelect.value = voice;
    this.styles.value = style;
    this._dom.offlineNote.classList.toggle('hidden', this._online);
    return { voice, style };
  }

  _fillVoices(voices) {
    const groups = {};
    voices.forEach((v) => {
      if (!groups[v.lang]) {
        groups[v.lang] = document.createElement('optgroup');
        groups[v.lang].label = t(`voice.lang.${v.lang}`);
      }
      const opt = document.createElement('option');
      opt.value = v.id;
      opt.dataset.type = v.type;
      opt.dataset.name = v.label;
      /* Nel menu solo genere e connessione: il resto è nella riga sotto, che non si taglia */
      opt.textContent = [v.label, ...this._traits(v).slice(0, 2)].join(' · ');
      groups[v.lang].appendChild(opt);
    });
    /* Italiano per primo: è la lingua dei testi che l'app legge di più */
    const order = Object.keys(groups).sort((a, b) => (a === 'it' ? -1 : b === 'it' ? 1 : 0));
    this._dom.voiceSelect.replaceChildren(...order.map(lang => groups[lang]));
  }

  _traits(v) {
    const traits = [t(`voice.gender.${v.gender}`)];
    if (v.type === 'edge' && !this._online) traits.push(t('voice.down'));
    else traits.push(t(v.type === 'edge' ? 'voice.online' : 'voice.offline'));
    if (v.multilingual) traits.push(t('voice.multi'));
    return traits;
  }

  /** Aggiorna riepilogo nel bottone, descrizione della voce e nota sugli stili. */
  refresh(voiceId, styleId) {
    const v = this._voices[voiceId];
    if (!v) return;
    const offline = v.type !== 'edge';
    this._dom.summary.textContent = t('panel.summary', {
      voice: v.label, style: offline ? this.styles.labelOf('neutro') : this.styles.labelOf(styleId),
    });
    this._dom.voiceDesc.textContent = this._traits(v).join(' · ');
    this._dom.styleNote.textContent = offline ? t('style.offlineNote', { voice: v.label }) : '';
    this._dom.styleNote.classList.toggle('hidden', !offline);
  }

  remember(voice, style) {
    savePref(VOICE_PREF_KEY, { voice, style, styleChosen: this.userChoseStyle() || false });
  }

  rememberStyleChoice(voice, style) {
    savePref(VOICE_PREF_KEY, { voice, style, styleChosen: true });
  }

  /** Lo stile automatico per tipo di file non sovrascrive una scelta esplicita. */
  userChoseStyle() {
    return loadPref(VOICE_PREF_KEY, {}).styleChosen === true;
  }

  showAutoStyle(styleId, ext) {
    this._dom.autoText.textContent = t('style.auto', { style: this.styles.labelOf(styleId), ext });
    this._dom.autoBar.classList.remove('hidden');
  }

  autoStyleVisible() {
    return !this._dom.autoBar.classList.contains('hidden');
  }

  hideAutoStyle() {
    this._dom.autoBar.classList.add('hidden');
  }
}
