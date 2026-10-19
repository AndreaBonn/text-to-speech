"""
titles.py
Titoli dei documenti sorgente, per i capitoli ID3 dell'MP3 salvato.

Affianca ``converters.file_a_testo`` senza cambiarne l'output: il testo letto
a voce resta lo stesso, i titoli servono solo a sapere dove inizia un capitolo.
"""

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.converters import _leggi_testo, _pulisci_markdown

log = logging.getLogger(__name__)

HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
_ATX_HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t#]*$", re.MULTILINE)
_FENCED_CODE = re.compile(r"`{1,3}.*?`{1,3}", re.DOTALL)


@dataclass(frozen=True)
class Titolo:
    """Titolo del documento sorgente.

    ``testo`` è il nome del capitolo; ``paragrafo`` è il testo del paragrafo
    con cui inizia nell'output di ``file_a_testo``. Di solito coincidono, ma
    l'HTML spezza ``<h1>Ciao <em>mondo</em></h1>`` in due paragrafi e il
    capitolo si aggancia al primo ("Ciao").
    """

    testo: str
    paragrafo: str


def estrai_titoli(percorso: Path) -> list[Titolo]:
    """Titoli del documento in ordine di lettura, per i capitoli dell'MP3.

    Affianca ``file_a_testo`` senza cambiarne l'output: il testo letto a voce
    resta lo stesso. PDF e TXT non hanno una struttura di titoli: lista vuota.
    """
    estrattori = {
        ".md": _titoli_markdown,
        ".epub": _titoli_epub,
        ".docx": _titoli_docx,
        ".html": _titoli_html,
        ".htm": _titoli_html,
    }
    estrattore = estrattori.get(percorso.suffix.lower())
    if not estrattore:
        return []
    try:
        return estrattore(percorso)
    except Exception:
        # Titles are optional metadata, and the parsers raise library-specific
        # errors (ebooklib, python-docx, bs4): a document whose text converts
        # must still load and save, just without chapters.
        log.warning("Titoli non estratti da %s, nessun capitolo.", percorso.name, exc_info=True)
        return []


def _titoli_markdown(percorso: Path) -> list[Titolo]:
    """Titoli dall'HTML di pandoc se c'è (come il testo), altrimenti regex sui ``#``."""
    if shutil.which("pandoc"):
        try:
            result = subprocess.run(
                ["pandoc", str(percorso), "-t", "html"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            log.warning("pandoc non ha risposto entro 30 s, titoli dal fallback regex.")
        else:
            if result.returncode == 0:
                from bs4 import BeautifulSoup

                # pandoc -t plain keeps a heading on one line: the paragraph is the whole title.
                soup = BeautifulSoup(result.stdout, "lxml")
                return [Titolo(t.testo, t.testo) for t in _titoli_da_soup(soup)]
            log.warning("pandoc ha restituito un errore, titoli dal fallback regex.")

    sorgente = _FENCED_CODE.sub("", _leggi_testo(percorso))
    titoli = []
    for match in _ATX_HEADING.finditer(sorgente):
        testo = _pulisci_markdown(match.group(1))
        if testo:
            titoli.append(Titolo(testo, testo))
    return titoli


def _titoli_docx(percorso: Path) -> list[Titolo]:
    """Paragrafi con stile Heading N o Title (Word salva in inglese i nomi degli stili base)."""
    from docx import Document

    titoli = []
    for p in Document(str(percorso)).paragraphs:
        nome_stile = (p.style.name if p.style is not None else "").lower()
        testo = p.text.strip()
        if testo and (nome_stile.startswith("heading") or nome_stile == "title"):
            titoli.append(Titolo(testo, testo))
    return titoli


def _titoli_html(percorso: Path) -> list[Titolo]:
    """Titoli dello stesso contenitore che legge ``_converti_html``."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(_leggi_testo(percorso), "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find("body") or soup
    return _titoli_da_soup(main)


def _titoli_epub(percorso: Path) -> list[Titolo]:
    """Titoli EPUB, con lo stesso ordine e la stessa pulizia di ``_converti_epub``."""
    import warnings

    import ebooklib
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    from ebooklib import epub

    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    book = epub.read_epub(str(percorso), options={"ignore_ncx": True})
    titoli = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        for tag in soup(["script", "style", "nav"]):
            tag.decompose()
        titoli.extend(_titoli_da_soup(soup))
    return titoli


def _titoli_da_soup(radice) -> list[Titolo]:
    """Un Titolo per ogni h1-h6; il paragrafo è il primo frammento che ``get_text`` ne ricava."""
    titoli = []
    for heading in radice.find_all(HEADING_TAGS):
        frammenti = [f.strip() for s in heading.strings for f in s.split("\n\n") if f.strip()]
        if frammenti:
            titoli.append(Titolo(" ".join(" ".join(frammenti).split()), frammenti[0]))
    return titoli
