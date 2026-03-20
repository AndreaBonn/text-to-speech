"""
converters.py
Convertitori da file di vari formati a testo piano per il TTS.

Formati supportati: .md, .txt, .epub, .docx, .html, .htm, .pdf
Ogni convertitore restituisce testo pulito pronto per la sintesi vocale.
"""

import logging
import re
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".md", ".txt", ".epub", ".docx", ".html", ".htm", ".pdf"}


def file_a_testo(percorso: Path) -> str:
    """Converte un file in testo piano in base all'estensione.

    Parameters
    ----------
    percorso : Path
        Percorso al file da convertire.

    Returns
    -------
    str
        Testo piano estratto dal file.

    Raises
    ------
    ValueError
        Se l'estensione del file non è supportata.
    """
    ext = percorso.suffix.lower()
    convertitori = {
        ".md": _converti_markdown,
        ".txt": _converti_testo,
        ".epub": _converti_epub,
        ".docx": _converti_docx,
        ".html": _converti_html,
        ".htm": _converti_html,
        ".pdf": _converti_pdf,
    }
    convertitore = convertitori.get(ext)
    if not convertitore:
        validi = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Formato '{ext}' non supportato. Formati validi: {validi}")
    return convertitore(percorso)


# ─── Testo puro ──────────────────────────────────────────────────────────────


def _converti_testo(percorso: Path) -> str:
    """Legge un file di testo puro. Nessuna conversione necessaria."""
    return percorso.read_text(encoding="utf-8").strip()


# ─── Markdown ─────────────────────────────────────────────────────────────────


def _converti_markdown(percorso: Path) -> str:
    """Converte Markdown in testo piano via pandoc o fallback regex.

    Usa pandoc se disponibile nel PATH, altrimenti un fallback regex
    che rimuove la sintassi Markdown più comune.
    """
    if shutil.which("pandoc"):
        result = subprocess.run(
            ["pandoc", str(percorso), "-t", "plain", "--wrap=none"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
        log.warning("pandoc ha restituito un errore, uso il fallback regex.")

    testo = percorso.read_text(encoding="utf-8")
    testo = re.sub(r"#{1,6}\s*", "", testo)
    testo = re.sub(r"\*\*(.+?)\*\*", r"\1", testo)
    testo = re.sub(r"\*(.+?)\*", r"\1", testo)
    testo = re.sub(r"`{1,3}.*?`{1,3}", "", testo, flags=re.DOTALL)
    testo = re.sub(r"!\[.*?\]\(.+?\)", "", testo)  # immagini (PRIMA dei link)
    testo = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", testo)  # link → solo testo
    testo = re.sub(r"[-*_]{3,}", "", testo)
    testo = re.sub(r"^\s*[-*+]\s+", "", testo, flags=re.MULTILINE)
    testo = re.sub(r"^\|.*\|$", "", testo, flags=re.MULTILINE)
    testo = re.sub(r"\n{3,}", "\n\n", testo)
    return testo.strip()


# ─── EPUB ─────────────────────────────────────────────────────────────────────


def _converti_epub(percorso: Path) -> str:
    """Estrae testo da un EPUB, capitolo per capitolo."""
    import warnings

    import ebooklib
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    from ebooklib import epub

    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    book = epub.read_epub(str(percorso), options={"ignore_ncx": True})
    testi = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        for tag in soup(["script", "style", "nav"]):
            tag.decompose()
        text = soup.get_text(separator="\n\n").strip()
        if text:
            testi.append(text)

    risultato = "\n\n".join(testi)
    risultato = re.sub(r"\n{3,}", "\n\n", risultato)
    return risultato.strip()


# ─── DOCX ─────────────────────────────────────────────────────────────────────


def _converti_docx(percorso: Path) -> str:
    """Estrae testo da un file Word (.docx) paragrafo per paragrafo."""
    from docx import Document

    doc = Document(str(percorso))
    paragrafi = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragrafi)


# ─── HTML ─────────────────────────────────────────────────────────────────────


def _converti_html(percorso: Path) -> str:
    """Estrae testo da una pagina HTML, rimuovendo navigazione e script."""
    from bs4 import BeautifulSoup

    html = percorso.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.find("body") or soup
    text = main.get_text(separator="\n\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ─── PDF ──────────────────────────────────────────────────────────────────────


def _converti_pdf(percorso: Path) -> str:
    """Estrae testo da un PDF pagina per pagina.

    Rimuove numeri di pagina isolati e normalizza spaziatura.
    Non gestisce PDF basati su immagini (serve OCR).
    """
    import pymupdf

    doc = pymupdf.open(str(percorso))
    testi = []

    for page in doc:
        text = page.get_text("text").strip()
        if text:
            testi.append(text)
    doc.close()

    risultato = "\n\n".join(testi)
    # Rimuovi numeri di pagina isolati (righe con solo 1-4 cifre)
    risultato = re.sub(r"^\s*\d{1,4}\s*$", "", risultato, flags=re.MULTILINE)
    risultato = re.sub(r"\n{3,}", "\n\n", risultato)
    return risultato.strip()
