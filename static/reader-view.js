'use strict';

/* ============================================================
   READER VIEW — testo intero, paragrafo in lettura evidenziato
   Un clic su un paragrafo chiede al player di leggere da lì.
============================================================ */
class ReaderView {
  /**
   * @param {HTMLElement} container  elemento che riceve i paragrafi
   * @param {(idx: number) => void} onSelect  chiamato al clic su un paragrafo
   */
  constructor(container, onSelect) {
    this._container = container;
    this._items = [];
    this._current = -1;
    container.addEventListener('click', (e) => {
      const p = e.target.closest('[data-idx]');
      if (p) onSelect(Number(p.dataset.idx));
    });
  }

  render(paragraphs) {
    const frag = document.createDocumentFragment();
    this._items = paragraphs.map((para) => {
      const p = document.createElement('p');
      p.className = 'reader-para';
      p.dataset.idx = String(para.idx);
      p.textContent = para.text;
      frag.appendChild(p);
      return p;
    });
    this._container.replaceChildren(frag);
    this._current = -1;
  }

  /** Evidenzia il paragrafo idx, attenua quelli già letti e lo porta in vista. */
  highlight(idx) {
    if (idx === this._current || !this._items[idx]) return;
    const lo = Math.min(idx, Math.max(this._current, 0));
    const hi = Math.max(idx, this._current);
    for (let i = lo; i <= hi; i++) {
      const el = this._items[i];
      el.classList.toggle('is-done', i < idx);
      el.classList.toggle('is-current', i === idx);
      if (i === idx) el.setAttribute('aria-current', 'true');
      else el.removeAttribute('aria-current');
    }
    this._current = idx;
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this._items[idx].scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
  }
}

/** Durata leggibile: "meno di un minuto", "circa 4 minuti", "circa 2 h e 10 min". */
function formatDuration(seconds) {
  if (seconds < 60) return t('duration.underMinute');
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return minutes === 1 ? t('duration.oneMinute') : t('duration.minutes', { n: minutes });
  }
  return t('duration.hours', { h: Math.floor(minutes / 60), m: minutes % 60 });
}
