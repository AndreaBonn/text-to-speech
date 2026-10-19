'use strict';

/* ============================================================
   PREFS — preferenze dell'utente salvate nel browser
   In una finestra privata o con lo storage bloccato le letture
   tornano al default e le scritture si perdono: la pagina funziona
   comunque, la preferenza vale solo per la sessione.
============================================================ */
function loadPref(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch (_) {
    return fallback;
  }
}

function savePref(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {
    /* Storage non disponibile: vedi nota in testa al file */
  }
}
