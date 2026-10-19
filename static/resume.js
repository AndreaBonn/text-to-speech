'use strict';

/* ============================================================
   RESUME — riprende un documento dal paragrafo dove ci si era fermati
============================================================ */
const POSITIONS_PREF_KEY = 'tts-reader-positions';
/* Oltre questo numero si dimenticano i documenti aperti meno di recente */
const MAX_REMEMBERED_DOCS = 30;

class ResumeStore {
  /**
   * Chiave del documento: nome, numero di paragrafi e impronta del testo.
   * Senza l'impronta due testi incollati diversi ("Testo incollato") con lo
   * stesso numero di paragrafi condividerebbero la posizione.
   */
  static keyFor(filename, paragraphs) {
    return `${filename}|${paragraphs.length}|${textFingerprint(paragraphs)}`;
  }

  static load(key) {
    const entry = loadPref(POSITIONS_PREF_KEY, []).find(e => e.key === key);
    return entry ? entry.idx : 0;
  }

  static save(key, idx) {
    const others = loadPref(POSITIONS_PREF_KEY, []).filter(e => e.key !== key);
    const next = idx > 0 ? [{ key, idx }, ...others] : others;
    savePref(POSITIONS_PREF_KEY, next.slice(0, MAX_REMEMBERED_DOCS));
  }
}

/** Hash djb2 del testo: identifica il documento, non serve a proteggerlo. */
function textFingerprint(paragraphs) {
  let hash = 5381;
  for (const p of paragraphs) {
    const text = p.text;
    for (let i = 0; i < text.length; i++) hash = ((hash * 33) ^ text.charCodeAt(i)) >>> 0;
  }
  return hash.toString(36);
}

class ResumeNote {
  constructor(onResume) {
    this._box = document.getElementById('resume-note');
    this._text = document.getElementById('resume-text');
    this._idx = 0;
    document.getElementById('btn-resume').addEventListener('click', () => {
      this.hide();
      onResume(this._idx);
    });
    document.getElementById('btn-resume-start').addEventListener('click', () => this.hide());
  }

  show(idx, total) {
    this._idx = idx;
    this._text.textContent = t('resume.text', { current: idx + 1, total });
    this._box.classList.remove('hidden');
  }

  hide() {
    this._box.classList.add('hidden');
  }
}
