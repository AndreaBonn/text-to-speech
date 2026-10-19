'use strict';
/* Applica il tema salvato prima del primo disegno, per evitare il lampo
   del tema scuro (S3). Script esterno perché la CSP vieta quelli inline. */
(function applySavedTheme() {
  try {
    if (JSON.parse(localStorage.getItem('tts-reader-theme')) === 'light') {
      document.documentElement.dataset.theme = 'light';
    }
  } catch (_) {
    /* Storage non disponibile: resta il tema scuro predefinito */
  }
})();
