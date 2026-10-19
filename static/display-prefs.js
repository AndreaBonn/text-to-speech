'use strict';

/* ============================================================
   DISPLAY PREFS — tema chiaro/scuro (S3) e dimensione del testo (S4)
============================================================ */
const THEME_PREF_KEY = 'tts-reader-theme';
const SCALE_PREF_KEY = 'tts-reader-text-scale';
const TEXT_SCALES = [0.85, 1, 1.15, 1.3, 1.5];

class DisplayPrefs {
  constructor() {
    this._themeBtn = document.getElementById('btn-theme');
    this._smaller  = document.getElementById('btn-text-smaller');
    this._larger   = document.getElementById('btn-text-larger');

    const savedScale = loadPref(SCALE_PREF_KEY, 1);
    this._scaleIdx = Math.max(0, TEXT_SCALES.indexOf(savedScale));
    if (TEXT_SCALES.indexOf(savedScale) < 0) this._scaleIdx = TEXT_SCALES.indexOf(1);

    this._themeBtn.addEventListener('click', () => this._toggleTheme());
    this._smaller.addEventListener('click', () => this._stepScale(-1));
    this._larger.addEventListener('click', () => this._stepScale(1));
    this._renderTheme();
    this._renderScale();
  }

  _isLight() {
    return document.documentElement.dataset.theme === 'light';
  }

  _toggleTheme() {
    if (this._isLight()) delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = 'light';
    savePref(THEME_PREF_KEY, this._isLight() ? 'light' : 'dark');
    this._renderTheme();
  }

  _renderTheme() {
    this._themeBtn.setAttribute('aria-pressed', String(this._isLight()));
  }

  _stepScale(delta) {
    const next = this._scaleIdx + delta;
    if (next < 0 || next >= TEXT_SCALES.length) return;
    this._scaleIdx = next;
    savePref(SCALE_PREF_KEY, TEXT_SCALES[next]);
    this._renderScale();
  }

  _renderScale() {
    document.documentElement.style.setProperty('--reading-scale', String(TEXT_SCALES[this._scaleIdx]));
    this._smaller.disabled = this._scaleIdx === 0;
    this._larger.disabled  = this._scaleIdx === TEXT_SCALES.length - 1;
  }
}
