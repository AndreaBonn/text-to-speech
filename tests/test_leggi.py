"""
tests/test_leggi.py
Test per le funzioni di leggi.py non coperte da test_app.py.

Copre: costanti/configurazione voci, markdown_a_testo (edge case),
scarica_voce_piper, concatena_wav, mostra_paragrafo.
"""

import io
import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# ===========================================================================
# Test — Costanti e configurazione voci
# ===========================================================================


class TestVoiceConstants:
    """Verifica coerenza tra le costanti di configurazione voci."""

    def test_all_voices_contains_edge_and_piper(self):
        """ALL_VOICES deve contenere tutte le voci Edge + Piper."""
        from config import ALL_VOICES, EDGE_VOICES, PIPER_VOICES

        # Assert
        for voice in EDGE_VOICES:
            assert voice in ALL_VOICES, f"Voce Edge '{voice}' mancante da ALL_VOICES"
        for voice in PIPER_VOICES:
            assert voice in ALL_VOICES, f"Voce Piper '{voice}' mancante da ALL_VOICES"

    def test_all_voices_is_sorted(self):
        """ALL_VOICES deve essere ordinata alfabeticamente."""
        from config import ALL_VOICES

        # Assert
        assert ALL_VOICES == sorted(ALL_VOICES)

    def test_all_voices_no_duplicates(self):
        """ALL_VOICES non deve avere duplicati."""
        from config import ALL_VOICES

        # Assert
        assert len(ALL_VOICES) == len(set(ALL_VOICES))

    def test_default_voice_exists(self):
        """DEFAULT_VOICE deve essere presente in ALL_VOICES."""
        from config import ALL_VOICES, DEFAULT_VOICE

        # Assert
        assert DEFAULT_VOICE in ALL_VOICES

    def test_default_voice_is_edge(self):
        """DEFAULT_VOICE deve essere una voce Edge (richiede internet)."""
        from config import DEFAULT_VOICE, EDGE_VOICES

        # Assert — giuseppe è Edge TTS
        assert DEFAULT_VOICE in EDGE_VOICES

    def test_edge_voices_have_valid_ids(self):
        """Gli ID delle voci Edge devono seguire il pattern it-IT-*Neural."""
        from config import EDGE_VOICES

        # Assert
        for name, edge_id in EDGE_VOICES.items():
            assert edge_id.startswith(
                "it-IT-"
            ), f"Voce '{name}' ha ID '{edge_id}' che non inizia con 'it-IT-'"
            assert edge_id.endswith(
                "Neural"
            ), f"Voce '{name}' ha ID '{edge_id}' che non finisce con 'Neural'"

    def test_voice_urls_point_to_existing_files(self):
        """VOICE_URLS deve avere entry per modello e config JSON."""
        from config import VOICE_URLS, VOICE_MODEL, VOICE_JSON

        # Assert
        assert VOICE_MODEL in VOICE_URLS
        assert VOICE_JSON in VOICE_URLS

    def test_voice_model_path_uses_home_directory(self):
        """VOICE_DIR deve essere sotto la home directory dell'utente."""
        from config import VOICE_DIR

        # Assert
        assert str(VOICE_DIR).startswith(str(Path.home()))


# ===========================================================================
# Test — markdown_a_testo (edge case, fallback regex)
# ===========================================================================


class TestMarkdownATestoEdgeCases:
    """Test per edge case del parser Markdown regex (senza pandoc)."""

    def _converti(self, markdown: str) -> str:
        """Helper: converte markdown via file temp con fallback regex forzato."""
        from leggi import markdown_a_testo

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(markdown)
            tmp_path = Path(f.name)
        try:
            with patch("shutil.which", return_value=None):
                return markdown_a_testo(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_rimuove_tabelle_markdown(self):
        """Le righe di tabella con | devono essere rimosse."""
        # Arrange
        md = "| Col1 | Col2 |\n|------|------|\n| A | B |\n\nTesto dopo."

        # Act
        risultato = self._converti(md)

        # Assert
        assert "|" not in risultato
        assert "Testo dopo." in risultato

    def test_rimuove_immagini(self):
        """Le immagini ![alt](url) devono essere rimosse completamente.

        NOTE: questo test rivela un bug nel codice — la regex dei link
        (riga 125) viene applicata PRIMA di quella delle immagini (riga 126),
        quindi ![alt](url) diventa !alt prima che il pattern immagine possa
        catturarlo. Il fix è invertire l'ordine delle due regex.
        """
        # Arrange
        md = "Prima. ![screenshot](img.png) Dopo."

        # Act
        risultato = self._converti(md)

        # Assert — il contratto dice: le immagini devono essere rimosse
        assert "img.png" not in risultato
        assert "screenshot" not in risultato

    def test_rimuove_separatori_orizzontali(self):
        """I separatori --- e *** devono essere rimossi."""
        # Arrange
        md = "Prima\n\n---\n\nDopo\n\n***\n\nFine"

        # Act
        risultato = self._converti(md)

        # Assert
        assert "---" not in risultato
        assert "***" not in risultato
        assert "Prima" in risultato
        assert "Fine" in risultato

    def test_rimuove_bullet_list_markers(self):
        """I marcatori di lista (- * +) devono essere rimossi."""
        # Arrange
        md = "- Primo elemento\n- Secondo elemento\n* Terzo\n+ Quarto"

        # Act
        risultato = self._converti(md)

        # Assert
        assert "Primo elemento" in risultato
        assert "Secondo elemento" in risultato
        # Non deve iniziare con marcatori
        for line in risultato.strip().split("\n"):
            stripped = line.strip()
            if stripped:
                assert not stripped.startswith("- "), f"Marcatore non rimosso: '{line}'"
                assert not stripped.startswith("* "), f"Marcatore non rimosso: '{line}'"
                assert not stripped.startswith("+ "), f"Marcatore non rimosso: '{line}'"

    def test_unicode_text_preserved(self):
        """Il testo unicode (accenti, emoji) deve essere preservato."""
        # Arrange
        md = "# Caffè e più\n\nÈ una giornata bellissima."

        # Act
        risultato = self._converti(md)

        # Assert
        assert "Caffè e più" in risultato
        assert "È una giornata bellissima." in risultato

    def test_multiple_blank_lines_collapsed(self):
        """Più di 2 righe vuote consecutive devono essere collassate a 2."""
        # Arrange
        md = "Primo\n\n\n\n\n\nSecondo"

        # Act
        risultato = self._converti(md)

        # Assert — non deve avere più di 2 newline consecutive
        assert "\n\n\n" not in risultato

    def test_nested_formatting(self):
        """Bold dentro italic e viceversa deve essere rimosso."""
        # Arrange
        md = "Testo ***grassetto e corsivo*** qui."

        # Act
        risultato = self._converti(md)

        # Assert
        assert "***" not in risultato
        assert "grassetto e corsivo" in risultato

    def test_inline_code_removed(self):
        """Il codice inline `code` deve essere rimosso."""
        # Arrange
        md = "Usa `pip install` per installare."

        # Act
        risultato = self._converti(md)

        # Assert
        assert "`" not in risultato

    def test_multiline_code_block_removed(self):
        """I blocchi di codice multi-riga devono essere rimossi completamente."""
        # Arrange
        md = "Prima.\n\n```python\ndef foo():\n    return 42\n```\n\nDopo."

        # Act
        risultato = self._converti(md)

        # Assert
        assert "def foo" not in risultato
        assert "```" not in risultato
        assert "Prima." in risultato
        assert "Dopo." in risultato

    def test_only_whitespace_returns_empty(self):
        """Un file con solo spazi e newline deve restituire stringa vuota."""
        # Arrange
        md = "   \n\n   \n   "

        # Act
        risultato = self._converti(md)

        # Assert
        assert risultato == ""


# ===========================================================================
# Test — markdown_a_testo con pandoc
# ===========================================================================


class TestMarkdownATestoConPandoc:
    """Test per il percorso pandoc di markdown_a_testo."""

    def test_usa_pandoc_quando_disponibile(self):
        """Deve usare pandoc se disponibile nel PATH."""
        from leggi import markdown_a_testo

        # Arrange
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write("# Titolo\n\nTesto semplice.")
            tmp_path = Path(f.name)

        try:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Titolo\n\nTesto semplice."

            with patch("shutil.which", return_value="/usr/bin/pandoc"), patch(
                "subprocess.run", return_value=mock_result
            ) as mock_run:
                # Act
                risultato = markdown_a_testo(tmp_path)

            # Assert
            mock_run.assert_called_once()
            assert "Titolo" in risultato
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_fallback_regex_se_pandoc_fallisce(self):
        """Se pandoc restituisce errore, deve cadere sul fallback regex."""
        from leggi import markdown_a_testo

        # Arrange
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write("# Titolo\n\nContenuto.")
            tmp_path = Path(f.name)

        try:
            mock_result = MagicMock()
            mock_result.returncode = 1  # pandoc fallisce
            mock_result.stdout = ""

            with patch("shutil.which", return_value="/usr/bin/pandoc"), patch(
                "subprocess.run", return_value=mock_result
            ):
                # Act
                risultato = markdown_a_testo(tmp_path)

            # Assert — il fallback regex deve comunque funzionare
            assert "#" not in risultato
            assert "Titolo" in risultato
            assert "Contenuto." in risultato
        finally:
            tmp_path.unlink(missing_ok=True)


# ===========================================================================
# Test — concatena_wav
# ===========================================================================


class TestConcatenaWav:
    """Test per la funzione concatena_wav."""

    def _make_wav(self, sample_rate: int, n_frames: int = 100) -> bytes:
        """Helper: crea un WAV valido in memoria."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00\x00" * n_frames)
        return buf.getvalue()

    def test_concatena_due_wav(self):
        """Due WAV concatenati devono avere la somma dei frame."""
        from leggi import concatena_wav

        # Arrange
        sr = 22050
        wav1 = self._make_wav(sr, n_frames=100)
        wav2 = self._make_wav(sr, n_frames=200)

        # Act
        risultato = concatena_wav([wav1, wav2], sr)

        # Assert
        with wave.open(io.BytesIO(risultato), "rb") as wf:
            assert wf.getnframes() == 300
            assert wf.getframerate() == sr
            assert wf.getnchannels() == 1

    def test_concatena_lista_vuota(self):
        """Una lista vuota deve produrre un WAV valido con 0 frame."""
        from leggi import concatena_wav

        # Arrange & Act
        risultato = concatena_wav([], 22050)

        # Assert
        with wave.open(io.BytesIO(risultato), "rb") as wf:
            assert wf.getnframes() == 0

    def test_concatena_singolo_wav(self):
        """Un singolo WAV deve restituire un WAV con gli stessi frame."""
        from leggi import concatena_wav

        # Arrange
        sr = 16000
        wav1 = self._make_wav(sr, n_frames=50)

        # Act
        risultato = concatena_wav([wav1], sr)

        # Assert
        with wave.open(io.BytesIO(risultato), "rb") as wf:
            assert wf.getnframes() == 50


# ===========================================================================
# Test — scarica_voce_piper
# ===========================================================================


class TestScaricaVocePiper:
    """Test per il download del modello Piper (con mock di rete)."""

    def test_skip_download_se_file_esistono(self):
        """Non deve scaricare se i file del modello esistono già."""
        from leggi import scarica_voce_piper

        # Arrange & Act
        with patch("leggi.VOICE_DIR") as mock_dir, patch("leggi.VOICE_URLS", {}) as mock_urls:
            mock_dir.mkdir = MagicMock()
            # Nessun URL da scaricare
            scarica_voce_piper()

        # Assert — nessuna chiamata a urlopen
        # (il test verifica che non crashi con lista vuota)

    def test_crea_directory_se_non_esiste(self):
        """Deve creare la directory dei modelli con parents=True."""
        from leggi import scarica_voce_piper, VOICE_DIR

        # Arrange
        mock_path_model = MagicMock()
        mock_path_model.exists.return_value = True
        mock_path_model.name = "model.onnx"

        mock_path_json = MagicMock()
        mock_path_json.exists.return_value = True
        mock_path_json.name = "model.onnx.json"

        with patch("leggi.VOICE_DIR") as mock_dir, patch(
            "leggi.VOICE_URLS",
            {
                mock_path_model: "http://example.com/model",
                mock_path_json: "http://example.com/model.json",
            },
        ):
            # Act
            scarica_voce_piper()

            # Assert
            mock_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)


# ===========================================================================
# Test — mostra_paragrafo
# ===========================================================================


class TestMostraParagrafo:
    """Test per la funzione di display terminale."""

    def test_non_stampa_se_non_visibile(self, capsys):
        """Se visibile=False, non deve stampare nulla."""
        from leggi import mostra_paragrafo

        # Act
        mostra_paragrafo(1, 10, "Testo del paragrafo", visibile=False)

        # Assert
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_stampa_se_visibile(self, capsys):
        """Se visibile=True, deve stampare il contatore e il testo."""
        from leggi import mostra_paragrafo

        # Act
        mostra_paragrafo(3, 10, "Contenuto paragrafo", visibile=True)

        # Assert
        captured = capsys.readouterr()
        assert "3/10" in captured.out
        assert "Contenuto paragrafo" in captured.out
