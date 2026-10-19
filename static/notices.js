'use strict';

/* ============================================================
   NOTICES — banner di errore con azione di recupero opzionale
   Il messaggio resta finché l'utente lo chiude o finché
   l'operazione successiva va a buon fine (clear()).
============================================================ */
class Notices {
  constructor() {
    this._banner = document.getElementById('error-banner');
    this._msg    = document.getElementById('error-banner-msg');
    this._action = document.getElementById('error-action');
    this._onAction = null;

    document.getElementById('btn-close-error')
      .addEventListener('click', () => this.clear());
    this._action.addEventListener('click', () => {
      const handler = this._onAction;
      this.clear();
      if (handler) handler();
    });
  }

  /**
   * Mostra un errore. `action` = {label, run} aggiunge un bottone
   * che propone la via d'uscita (es. passare alla voce offline).
   */
  error(message, action = null) {
    this._msg.textContent = message;
    this._onAction = action ? action.run : null;
    this._action.textContent = action ? action.label : '';
    this._action.classList.toggle('hidden', !action);
    this._banner.classList.remove('hidden');
  }

  clear() {
    this._banner.classList.add('hidden');
    this._onAction = null;
  }
}

/**
 * Legge il corpo di errore di una risposta API.
 * Restituisce {message, fallbackVoice}; message è null se il server
 * non ha mandato JSON (es. pagina HTML di un errore imprevisto).
 */
async function readApiError(res) {
  try {
    const data = await res.json();
    return { message: data.error || null, fallbackVoice: data.fallback_voice || null };
  } catch (_) {
    return { message: null, fallbackVoice: null };
  }
}
