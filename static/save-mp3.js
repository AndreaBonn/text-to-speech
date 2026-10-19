'use strict';

/* ============================================================
   SAVE MP3 — salvataggio del testo intero con avanzamento reale
============================================================ */
const SAVE_POLL_MS = 1000;
const SAVE_DONE_VISIBLE_MS = 6000;

/**
 * Chiede al server l'MP3 completo. Mentre la richiesta è in corso legge
 * /api/save/progress e chiama onProgress(done, total).
 * Restituisce la Response; se ok, anche blob e nome file proposto dal server.
 */
async function requestMp3(voice, style, onProgress) {
  const poll = setInterval(async () => {
    try {
      const p = await (await fetch('/api/save/progress')).json();
      if (p.active && p.total) onProgress(p.done, p.total);
    } catch (_) {
      /* Un giro di polling perso non cambia l'esito: il prossimo aggiorna */
    }
  }, SAVE_POLL_MS);
  try {
    const res = await fetch(`/api/save?lang=${i18nGetLang()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice, style }),
    });
    if (!res.ok) return { res };
    const blob = await res.blob();
    return { res, blob, filename: filenameFromDisposition(res.headers.get('Content-Disposition')) };
  } finally {
    clearInterval(poll);
  }
}

/** Nome file da Content-Disposition, preferendo la forma UTF-8 (RFC 5987). */
function filenameFromDisposition(header) {
  if (!header) return null;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star) {
    try { return decodeURIComponent(star[1]); } catch (_) { /* forma semplice sotto */ }
  }
  const plain = /filename="([^"]+)"/i.exec(header);
  return plain ? plain[1] : null;
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href     = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
