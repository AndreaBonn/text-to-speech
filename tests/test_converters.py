"""
tests/test_converters.py
Test per il modulo converters.py: dispatcher e convertitori di formato.

Ogni convertitore è testato con file reali creati in tmp_path.
"""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.converters import SUPPORTED_EXTENSIONS, file_a_testo
from src.titles import estrai_titoli

# ===========================================================================
# Test — Dispatcher file_a_testo
# ===========================================================================


class TestFileATesto:
    """Test per il dispatcher principale."""

    def test_estensione_non_supportata_solleva_errore(self, tmp_path):
        """Un file con estensione non supportata deve sollevare ValueError."""
        # Arrange
        file_csv = tmp_path / "dati.csv"
        file_csv.write_text("a,b,c")

        # Act & Assert
        with pytest.raises(ValueError, match="non supportato"):
            file_a_testo(file_csv)

    def test_supported_extensions_contiene_tutti_i_formati(self):
        """SUPPORTED_EXTENSIONS deve contenere tutti i formati dichiarati."""
        # Assert
        attesi = {".md", ".txt", ".epub", ".docx", ".html", ".htm", ".pdf"}
        assert attesi == SUPPORTED_EXTENSIONS

    def test_dispatcher_case_insensitive(self, tmp_path):
        """L'estensione deve essere case-insensitive."""
        # Arrange
        file_txt = tmp_path / "test.TXT"
        file_txt.write_text("Contenuto del file.")

        # Act
        risultato = file_a_testo(file_txt)

        # Assert
        assert risultato == "Contenuto del file."


# ===========================================================================
# Test — Convertitore .txt
# ===========================================================================


class TestConvertiTesto:
    """Test per il convertitore di file testo puro."""

    def test_legge_testo_semplice(self, tmp_path):
        """Un file .txt deve essere letto e restituito invariato."""
        # Arrange
        txt = tmp_path / "nota.txt"
        txt.write_text("Questa è una nota semplice.")

        # Act
        risultato = file_a_testo(txt)

        # Assert
        assert risultato == "Questa è una nota semplice."

    def test_strip_whitespace(self, tmp_path):
        """Spazi iniziali e finali devono essere rimossi."""
        # Arrange
        txt = tmp_path / "spazi.txt"
        txt.write_text("  \n\nContenuto con spazi.\n\n  ")

        # Act
        risultato = file_a_testo(txt)

        # Assert
        assert risultato == "Contenuto con spazi."

    def test_file_vuoto(self, tmp_path):
        """Un file vuoto deve restituire stringa vuota."""
        # Arrange
        txt = tmp_path / "vuoto.txt"
        txt.write_text("")

        # Act
        risultato = file_a_testo(txt)

        # Assert
        assert risultato == ""

    def test_unicode_preservato(self, tmp_path):
        """Caratteri unicode (accenti, emoji) devono essere preservati."""
        # Arrange
        txt = tmp_path / "unicode.txt"
        txt.write_text("Caffè, più, naïve, 日本語")

        # Act
        risultato = file_a_testo(txt)

        # Assert
        assert "Caffè" in risultato
        assert "日本語" in risultato

    def test_paragrafi_multipli(self, tmp_path):
        """Più paragrafi separati da righe vuote devono essere preservati."""
        # Arrange
        txt = tmp_path / "multi.txt"
        txt.write_text("Primo paragrafo.\n\nSecondo paragrafo.\n\nTerzo.")

        # Act
        risultato = file_a_testo(txt)

        # Assert
        assert "Primo paragrafo." in risultato
        assert "Secondo paragrafo." in risultato
        assert "Terzo." in risultato


# ===========================================================================
# Test — Convertitore .md (delega a leggi)
# ===========================================================================


class TestConvertiMarkdown:
    """Test per il convertitore Markdown (delega a markdown_a_testo)."""

    def test_rimuove_header_markdown(self, tmp_path):
        """I titoli # devono essere rimossi dal testo."""
        # Arrange
        md = tmp_path / "doc.md"
        md.write_text("# Titolo\n\nContenuto del documento.")

        # Act — forza fallback regex (senza pandoc)
        with patch("src.converters.shutil.which", return_value=None):
            risultato = file_a_testo(md)

        # Assert
        assert "#" not in risultato
        assert "Titolo" in risultato
        assert "Contenuto del documento." in risultato

    def test_pandoc_disponibile_argv_completo_e_stdout_restituito(self, tmp_path):
        """Con pandoc nel PATH: argv esatto e restituito lo stdout di pandoc."""
        # Arrange
        md = tmp_path / "doc.md"
        md.write_text("# Titolo\n\nTesto.")
        completato = MagicMock(returncode=0, stdout="OUTPUT-DI-PANDOC\n")

        # Act
        with (
            patch("src.converters.shutil.which", return_value="/usr/bin/pandoc"),
            patch("src.converters.subprocess.run", return_value=completato) as run,
        ):
            risultato = file_a_testo(md)

        # Assert
        assert run.call_count == 1
        assert run.call_args.args[0] == [
            "pandoc",
            str(md),
            "-t",
            "plain",
            "--wrap=none",
        ]
        assert risultato == "OUTPUT-DI-PANDOC\n"

    def test_pandoc_in_timeout_usa_fallback_regex(self, tmp_path):
        """pandoc bloccato su un file enorme: si legge comunque col fallback."""
        import subprocess

        md = tmp_path / "doc.md"
        md.write_text("# Titolo\n\nCorpo **importante**.")

        with (
            patch("src.converters.shutil.which", return_value="/usr/bin/pandoc"),
            patch(
                "src.converters.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["pandoc"], 30),
            ),
        ):
            risultato = file_a_testo(md)

        assert risultato == "Titolo\n\nCorpo importante."

    def test_pandoc_errore_usa_fallback_regex(self, tmp_path):
        """Se pandoc esce con errore si usa il fallback regex sul file."""
        # Arrange
        md = tmp_path / "doc.md"
        md.write_text("# Titolo\n\nTesto.")
        fallito = MagicMock(returncode=1, stdout="STDOUT-DA-IGNORARE")

        # Act
        with (
            patch("src.converters.shutil.which", return_value="/usr/bin/pandoc"),
            patch("src.converters.subprocess.run", return_value=fallito),
        ):
            risultato = file_a_testo(md)

        # Assert
        assert risultato == "Titolo\n\nTesto."

    def test_fallback_rimuove_titolo_di_livello_6(self, tmp_path):
        """Anche i titoli fino a livello 6 (######) perdono il marcatore."""
        # Arrange
        md = tmp_path / "h6.md"
        md.write_text("###### H6 titolo\n\nCorpo.")

        # Act
        with patch("src.converters.shutil.which", return_value=None):
            risultato = file_a_testo(md)

        # Assert
        assert risultato == "H6 titolo\n\nCorpo."

    def test_fallback_rimuove_separatore_underscore(self, tmp_path):
        """Il separatore '___' è rimosso, il testo attorno resta."""
        # Arrange
        md = tmp_path / "sep.md"
        md.write_text("Prima.\n\n___\n\nDopo.")

        # Act
        with patch("src.converters.shutil.which", return_value=None):
            risultato = file_a_testo(md)

        # Assert
        assert "_" not in risultato
        assert risultato == "Prima.\n\nDopo."

    def test_fallback_comprime_righe_vuote_multiple(self, tmp_path):
        """Tre o più righe vuote consecutive diventano un solo separatore."""
        # Arrange
        md = tmp_path / "vuote.md"
        md.write_text("Primo.\n\n\n\n\nSecondo.")

        # Act
        with patch("src.converters.shutil.which", return_value=None):
            risultato = file_a_testo(md)

        # Assert
        assert risultato == "Primo.\n\nSecondo."


# ===========================================================================
# Test — Convertitore .docx
# ===========================================================================


class TestConvertiDocx:
    """Test per il convertitore Word DOCX."""

    def test_estrae_paragrafi(self, tmp_path):
        """Un DOCX con paragrafi deve restituire il testo separato."""
        from docx import Document

        # Arrange
        docx_path = tmp_path / "documento.docx"
        doc = Document()
        doc.add_paragraph("Primo paragrafo del documento.")
        doc.add_paragraph("Secondo paragrafo con contenuto.")
        doc.save(str(docx_path))

        # Act
        risultato = file_a_testo(docx_path)

        # Assert
        assert "Primo paragrafo del documento." in risultato
        assert "Secondo paragrafo con contenuto." in risultato

    def test_ignora_paragrafi_vuoti(self, tmp_path):
        """Paragrafi vuoti nel DOCX devono essere ignorati."""
        from docx import Document

        # Arrange
        docx_path = tmp_path / "vuoti.docx"
        doc = Document()
        doc.add_paragraph("Testo valido.")
        doc.add_paragraph("")  # vuoto
        doc.add_paragraph("   ")  # solo spazi
        doc.add_paragraph("Altro testo.")
        doc.save(str(docx_path))

        # Act
        risultato = file_a_testo(docx_path)

        # Assert
        assert risultato == "Testo valido.\n\nAltro testo."

    def test_docx_vuoto(self, tmp_path):
        """Un DOCX senza contenuto deve restituire stringa vuota."""
        from docx import Document

        # Arrange
        docx_path = tmp_path / "empty.docx"
        doc = Document()
        doc.save(str(docx_path))

        # Act
        risultato = file_a_testo(docx_path)

        # Assert
        assert risultato == ""


# ===========================================================================
# Test — Convertitore .html
# ===========================================================================


class TestConvertiHtml:
    """Test per il convertitore HTML."""

    def test_estrae_testo_body(self, tmp_path):
        """Il testo del body deve essere estratto."""
        # Arrange
        html = tmp_path / "pagina.html"
        html.write_text("""<!DOCTYPE html>
<html><head><title>Test</title></head>
<body><h1>Titolo</h1><p>Contenuto della pagina.</p></body>
</html>""")

        # Act
        risultato = file_a_testo(html)

        # Assert
        assert "Titolo" in risultato
        assert "Contenuto della pagina." in risultato

    def test_rimuove_script_e_style(self, tmp_path):
        """Tag script e style devono essere rimossi."""
        # Arrange
        html = tmp_path / "scripts.html"
        html.write_text("""<html><body>
<script>alert('xss')</script>
<style>body { color: red; }</style>
<p>Testo visibile.</p>
</body></html>""")

        # Act
        risultato = file_a_testo(html)

        # Assert
        assert "alert" not in risultato
        assert "color: red" not in risultato
        assert "Testo visibile." in risultato

    def test_rimuove_nav_header_footer(self, tmp_path):
        """Elementi di navigazione devono essere rimossi."""
        # Arrange
        html = tmp_path / "layout.html"
        html.write_text("""<html><body>
<nav><a href="/">Home</a><a href="/about">About</a></nav>
<header><h1>Header del sito</h1></header>
<main><p>Contenuto principale.</p></main>
<footer><p>Copyright 2025</p></footer>
</body></html>""")

        # Act
        risultato = file_a_testo(html)

        # Assert
        assert "Contenuto principale." in risultato
        assert "Home" not in risultato
        assert "About" not in risultato
        assert "Header del sito" not in risultato
        assert "Copyright" not in risultato

    def test_preferisce_main_content(self, tmp_path):
        """Se presente, deve estrarre da <main>, escludendo il resto del body."""
        # Arrange
        html = tmp_path / "article.html"
        html.write_text("""<html><body>
<div class="sidebar">Menu laterale con molto testo.</div>
<main><p>Articolo importante.</p></main>
</body></html>""")

        # Act
        risultato = file_a_testo(html)

        # Assert
        assert "Articolo importante." in risultato
        assert "Menu laterale" not in risultato
        assert risultato == "Articolo importante."

    def test_preferisce_article_se_manca_main(self, tmp_path):
        """Senza <main>, il contenuto è quello di <article>, non del resto."""
        # Arrange
        html = tmp_path / "solo_article.html"
        html.write_text("""<html><body>
<div>Testo fuori dall'articolo.</div>
<article><p>Corpo dell'articolo.</p></article>
</body></html>""")

        # Act
        risultato = file_a_testo(html)

        # Assert
        assert risultato == "Corpo dell'articolo."

    def test_senza_main_rimuove_nav_header_footer_aside(self, tmp_path):
        """Senza <main> né <article> i blocchi di contorno non finiscono nel testo."""
        # Arrange
        html = tmp_path / "senza_main.html"
        html.write_text("""<html><body>
<nav><a href="/">Voce di navigazione</a></nav>
<header><h1>Intestazione sito</h1></header>
<aside>Box laterale pubblicitario</aside>
<p>Contenuto centrale.</p>
<footer><p>Piè di pagina legale</p></footer>
</body></html>""")

        # Act
        risultato = file_a_testo(html)

        # Assert
        assert risultato == "Contenuto centrale."
        assert "navigazione" not in risultato
        assert "Intestazione" not in risultato
        assert "laterale" not in risultato
        assert "legale" not in risultato

    def test_html_estensione_htm(self, tmp_path):
        """Anche .htm deve funzionare come .html."""
        # Arrange
        htm = tmp_path / "pagina.htm"
        htm.write_text("<html><body><p>Testo HTM.</p></body></html>")

        # Act
        risultato = file_a_testo(htm)

        # Assert
        assert "Testo HTM." in risultato


# ===========================================================================
# Test — Convertitore .pdf
# ===========================================================================


class TestConvertiPdf:
    """Test per il convertitore PDF."""

    def test_estrae_testo_da_pdf(self, tmp_path):
        """Un PDF con testo deve essere estratto correttamente."""
        import pymupdf

        # Arrange — crea un PDF di test con pymupdf
        pdf_path = tmp_path / "documento.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Primo paragrafo del documento PDF.")
        page.insert_text((72, 120), "Secondo paragrafo con contenuto.")
        doc.save(str(pdf_path))
        doc.close()

        # Act
        risultato = file_a_testo(pdf_path)

        # Assert
        assert "Primo paragrafo del documento PDF." in risultato
        assert "Secondo paragrafo con contenuto." in risultato

    def test_pdf_multipagina(self, tmp_path):
        """Un PDF con più pagine deve estrarre testo da tutte."""
        import pymupdf

        # Arrange
        pdf_path = tmp_path / "multi.pdf"
        doc = pymupdf.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text((72, 72), f"Contenuto pagina {i + 1}.")
        doc.save(str(pdf_path))
        doc.close()

        # Act
        risultato = file_a_testo(pdf_path)

        # Assert
        assert "Contenuto pagina 1." in risultato
        assert "Contenuto pagina 2." in risultato
        assert "Contenuto pagina 3." in risultato

    def test_rimuove_numeri_pagina_isolati(self, tmp_path):
        """Numeri di pagina isolati su una riga devono essere rimossi."""
        import pymupdf

        # Arrange
        pdf_path = tmp_path / "paginato.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Testo del documento.")
        page.insert_text((300, 780), "1")  # numero di pagina in basso
        doc.save(str(pdf_path))
        doc.close()

        # Act
        risultato = file_a_testo(pdf_path)

        # Assert
        assert "Testo del documento." in risultato
        # Il numero "1" isolato deve essere rimosso
        lines = [line.strip() for line in risultato.split("\n") if line.strip()]
        assert "1" not in lines

    def test_pdf_pagina_vuota_in_mezzo_ignorata(self, tmp_path):
        """Una pagina senza testo non lascia buchi: le altre restano separate da riga vuota."""
        import pymupdf

        # Arrange
        pdf_path = tmp_path / "buco.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "Pagina uno.")
        doc.new_page()  # vuota
        doc.new_page().insert_text((72, 72), "Pagina tre.")
        doc.save(str(pdf_path))
        doc.close()

        # Act
        risultato = file_a_testo(pdf_path)

        # Assert
        assert risultato == "Pagina uno.\n\nPagina tre."

    def test_pdf_solo_pagine_vuote_restituisce_stringa_vuota(self, tmp_path):
        """Un PDF di sole pagine bianche non produce testo."""
        import pymupdf

        # Arrange
        pdf_path = tmp_path / "bianco.pdf"
        doc = pymupdf.open()
        doc.new_page()
        doc.new_page()
        doc.save(str(pdf_path))
        doc.close()

        # Act
        risultato = file_a_testo(pdf_path)

        # Assert
        assert risultato == ""


# ===========================================================================
# Test — Convertitore .epub
# ===========================================================================


class TestConvertiEpub:
    """Test per il convertitore EPUB."""

    def _make_epub(self, tmp_path: Path, capitoli: list[str]) -> Path:
        """Helper: crea un EPUB minimale con i capitoli dati."""
        from ebooklib import epub

        book = epub.EpubBook()
        book.set_identifier("test-id-123")
        book.set_title("Test Book")
        book.set_language("it")

        items = []
        for i, testo in enumerate(capitoli):
            ch = epub.EpubHtml(
                title=f"Capitolo {i + 1}",
                file_name=f"chap_{i}.xhtml",
                lang="it",
            )
            ch.content = f"<html><body><p>{testo}</p></body></html>".encode()
            book.add_item(ch)
            items.append(ch)

        book.toc = items
        book.spine = ["nav", *items]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        epub_path = tmp_path / "libro.epub"
        epub.write_epub(str(epub_path), book)
        return epub_path

    def test_estrae_testo_capitoli(self, tmp_path):
        """Un EPUB con capitoli deve estrarre il testo di ciascuno."""
        # Arrange
        epub_path = self._make_epub(
            tmp_path,
            ["Contenuto del primo capitolo.", "Contenuto del secondo capitolo."],
        )

        # Act
        risultato = file_a_testo(epub_path)

        # Assert
        assert "Contenuto del primo capitolo." in risultato
        assert "Contenuto del secondo capitolo." in risultato

    def test_epub_singolo_capitolo(self, tmp_path):
        """Un EPUB con un solo capitolo deve funzionare."""
        # Arrange
        epub_path = self._make_epub(tmp_path, ["Unico capitolo del libro."])

        # Act
        risultato = file_a_testo(epub_path)

        # Assert
        assert "Unico capitolo del libro." in risultato

    def test_epub_rimuove_script(self, tmp_path):
        """Eventuali tag script nell'EPUB devono essere rimossi."""
        from ebooklib import epub

        # Arrange
        book = epub.EpubBook()
        book.set_identifier("test-script")
        book.set_title("Script Test")
        book.set_language("it")

        ch = epub.EpubHtml(title="Cap", file_name="ch.xhtml", lang="it")
        ch.content = b"""<html><body>
<script>alert('evil')</script>
<p>Testo sicuro.</p>
</body></html>"""
        book.add_item(ch)
        book.spine = ["nav", ch]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        epub_path = tmp_path / "script.epub"
        epub.write_epub(str(epub_path), book)

        # Act
        risultato = file_a_testo(epub_path)

        # Assert
        assert "alert" not in risultato
        assert "Testo sicuro." in risultato

    def test_epub_capitoli_separati_da_riga_vuota(self, tmp_path):
        """Due capitoli sono uniti con una riga vuota (un paragrafo ciascuno)."""
        # Arrange
        epub_path = self._make_epub(tmp_path, ["Capitolo A testo.", "Capitolo B testo."])

        # Act
        risultato = file_a_testo(epub_path)

        # Assert
        assert risultato == "Capitolo A testo.\n\nCapitolo B testo."

    def test_epub_rimuove_nav_nel_capitolo(self, tmp_path):
        """Un <nav> dentro un capitolo (es. indice) non finisce nel testo."""
        from ebooklib import epub

        # Arrange
        book = epub.EpubBook()
        book.set_identifier("test-nav")
        book.set_title("Nav Test")
        book.set_language("it")
        ch = epub.EpubHtml(title="Cap", file_name="ch.xhtml", lang="it")
        ch.content = b"""<html><body>
<nav><ol><li>Indice interno</li></ol></nav>
<p>Testo del capitolo.</p>
</body></html>"""
        book.add_item(ch)
        book.spine = ["nav", ch]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        epub_path = tmp_path / "nav.epub"
        epub.write_epub(str(epub_path), book)

        # Act
        risultato = file_a_testo(epub_path)

        # Assert
        assert risultato == "Testo del capitolo."
        assert "Indice interno" not in risultato


class TestCodificaFileDiTesto:
    """File salvati da Blocco note o da vecchi editor: UTF-8 con BOM o Windows-1252."""

    def test_txt_windows_1252_letto_con_accenti(self, tmp_path):
        txt = tmp_path / "nota.txt"
        txt.write_bytes("Città è bella, perché sì: l\u2019ingresso costa 5 €.".encode("cp1252"))

        assert file_a_testo(txt) == "Città è bella, perché sì: l\u2019ingresso costa 5 €."

    def test_txt_utf8_con_bom_senza_carattere_bom(self, tmp_path):
        txt = tmp_path / "nota.txt"
        txt.write_bytes("Testo con BOM.".encode("utf-8-sig"))

        assert file_a_testo(txt) == "Testo con BOM."

    def test_txt_utf8_resta_invariato(self, tmp_path):
        txt = tmp_path / "nota.txt"
        txt.write_bytes("Perché è così: “citazione” €.".encode())

        assert file_a_testo(txt) == "Perché è così: “citazione” €."

    def test_markdown_windows_1252_nel_fallback(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_bytes("# Titolo\n\nUnità di misura.".encode("cp1252"))

        with patch("src.converters.shutil.which", return_value=None):
            risultato = file_a_testo(md)

        assert risultato == "Titolo\n\nUnità di misura."

    def test_html_windows_1252_letto_con_accenti(self, tmp_path):
        html = tmp_path / "pagina.html"
        html.write_bytes("<html><body><p>Città antica.</p></body></html>".encode("cp1252"))

        assert file_a_testo(html) == "Città antica."

    def test_txt_windows_a_capo_crlf_divide_i_paragrafi(self, tmp_path):
        txt = tmp_path / "nota.txt"
        txt.write_bytes("Città.\r\n\r\nPerché.".encode("cp1252"))

        assert file_a_testo(txt) == "Città.\n\nPerché."

    def test_txt_utf16_non_diventa_testo_illeggibile(self, tmp_path):
        txt = tmp_path / "nota.txt"
        txt.write_bytes("Ciao".encode("utf-16"))

        with pytest.raises(UnicodeDecodeError):
            file_a_testo(txt)


# ===========================================================================
# Test — estrai_titoli
# ===========================================================================

MARKDOWN_TRE_TITOLI = (
    "# Primo **titolo**\n\nTesto uno.\n\n## Secondo\n\nTesto due.\n\n# Terzo\n\nTesto tre.\n"
)


def _capitoli(percorso: Path) -> list[tuple[int, str]]:
    """Titoli agganciati ai paragrafi che il motore leggerebbe davvero."""
    from src.chapters import trova_capitoli

    paragrafi = [p.strip() for p in file_a_testo(percorso).split("\n\n") if p.strip()]
    return trova_capitoli(paragrafi, estrai_titoli(percorso))


class TestEstraiTitoli:
    """I titoli devono agganciarsi ai paragrafi prodotti da file_a_testo."""

    def test_markdown_fallback_regex(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text(MARKDOWN_TRE_TITOLI)

        with patch("src.converters.shutil.which", return_value=None):
            titoli = [t.testo for t in estrai_titoli(md)]
            capitoli = _capitoli(md)

        assert titoli == ["Primo titolo", "Secondo", "Terzo"]
        assert capitoli == [(0, "Primo titolo"), (2, "Secondo"), (4, "Terzo")]

    def test_markdown_fallback_ignora_cancelletto_nei_blocchi_di_codice(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Vero\n\n```\n# commento\n```\n\nTesto.\n")

        with patch("src.converters.shutil.which", return_value=None):
            titoli = [t.testo for t in estrai_titoli(md)]

        assert titoli == ["Vero"]

    @pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc non installato")
    def test_markdown_con_pandoc(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text(MARKDOWN_TRE_TITOLI + "\nQuarto *corsivo*\n======\n\nTesto quattro.\n")

        capitoli = _capitoli(md)

        assert capitoli == [
            (0, "Primo titolo"),
            (2, "Secondo"),
            (4, "Terzo"),
            (6, "Quarto corsivo"),
        ]

    def test_markdown_pandoc_in_errore_usa_il_fallback(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Titolo\n\nTesto.")

        with (
            patch("src.converters.shutil.which", return_value="/usr/bin/pandoc"),
            patch("src.converters.subprocess.run", return_value=MagicMock(returncode=1)),
        ):
            titoli = [t.testo for t in estrai_titoli(md)]

        assert titoli == ["Titolo"]

    def test_docx_stili_heading(self, tmp_path):
        from docx import Document

        docx_path = tmp_path / "doc.docx"
        doc = Document()
        doc.add_heading("Capitolo uno", level=1)
        doc.add_paragraph("Testo uno.")
        doc.add_heading("Sezione", level=2)
        doc.add_paragraph("Testo due.")
        doc.save(str(docx_path))

        assert _capitoli(docx_path) == [(0, "Capitolo uno"), (2, "Sezione")]

    def test_html_titolo_con_markup_interno(self, tmp_path):
        html = tmp_path / "pagina.html"
        html.write_text(
            "<html><body><nav><h2>Menu</h2></nav><main>"
            "<h1>Ciao <em>mondo</em></h1><p>Testo uno.</p>"
            "<h2>Seconda parte</h2><p>Testo due.</p>"
            "</main></body></html>"
        )

        assert [t.testo for t in estrai_titoli(html)] == ["Ciao mondo", "Seconda parte"]
        assert _capitoli(html) == [(0, "Ciao mondo"), (3, "Seconda parte")]

    def test_epub_titoli_dei_capitoli(self, tmp_path):
        from ebooklib import epub

        book = epub.EpubBook()
        book.set_identifier("id-titoli")
        book.set_title("Libro")
        book.set_language("it")
        capitoli = []
        for i, nome in enumerate(["Inizio", "Fine"]):
            ch = epub.EpubHtml(title=nome, file_name=f"c{i}.xhtml", lang="it")
            ch.content = f"<html><body><h1>{nome}</h1><p>Testo {i}.</p></body></html>".encode()
            book.add_item(ch)
            capitoli.append(ch)
        book.toc = capitoli
        book.spine = ["nav", *capitoli]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        epub_path = tmp_path / "libro.epub"
        epub.write_epub(str(epub_path), book)

        trovati = _capitoli(epub_path)

        assert [titolo for _, titolo in trovati] == ["Inizio", "Fine"]
        assert trovati[0][0] < trovati[1][0]

    def test_txt_nessun_titolo(self, tmp_path):
        txt = tmp_path / "note.txt"
        txt.write_text("# Sembra un titolo\n\nTesto.")

        assert estrai_titoli(txt) == []

    def test_pdf_nessun_titolo(self, tmp_path):
        import pymupdf

        pdf_path = tmp_path / "doc.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "Testo del PDF.")
        doc.save(str(pdf_path))
        doc.close()

        assert estrai_titoli(pdf_path) == []

    def test_file_illeggibile_nessun_titolo(self, tmp_path):
        """I titoli sono opzionali: un estrattore che fallisce non blocca il caricamento."""
        rotto = tmp_path / "rotto.docx"
        rotto.write_bytes(b"non uno zip")

        assert estrai_titoli(rotto) == []
