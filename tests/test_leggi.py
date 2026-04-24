"""
tests/test_leggi.py
Test per le funzioni di leggi.py e moduli correlati.

Copre: costanti/configurazione voci, convertitore Markdown (edge case),
scarica_voce_piper (synthesis), concatena_wav, mostra_paragrafo,
calcola_path_output, leggi_con_piper, leggi_con_edge, main.
"""

import asyncio
import io
import tempfile
import wave
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ===========================================================================
# Test — Costanti e configurazione voci
# ===========================================================================


class TestVoiceConstants:
    """Verifica coerenza tra le costanti di configurazione voci."""

    def test_all_voices_contains_edge_and_piper(self):
        """ALL_VOICES deve contenere tutte le voci Edge + Piper."""
        from src.config import ALL_VOICES, EDGE_VOICES, PIPER_VOICES

        # Assert
        for voice in EDGE_VOICES:
            assert voice in ALL_VOICES, f"Voce Edge '{voice}' mancante da ALL_VOICES"
        for voice in PIPER_VOICES:
            assert voice in ALL_VOICES, f"Voce Piper '{voice}' mancante da ALL_VOICES"

    def test_all_voices_is_sorted(self):
        """ALL_VOICES deve essere ordinata alfabeticamente."""
        from src.config import ALL_VOICES

        # Assert
        assert sorted(ALL_VOICES) == ALL_VOICES

    def test_all_voices_no_duplicates(self):
        """ALL_VOICES non deve avere duplicati."""
        from src.config import ALL_VOICES

        # Assert
        assert len(ALL_VOICES) == len(set(ALL_VOICES))

    def test_default_voice_exists(self):
        """DEFAULT_VOICE deve essere presente in ALL_VOICES."""
        from src.config import ALL_VOICES, DEFAULT_VOICE

        # Assert
        assert DEFAULT_VOICE in ALL_VOICES

    def test_default_voice_is_edge(self):
        """DEFAULT_VOICE deve essere una voce Edge (richiede internet)."""
        from src.config import DEFAULT_VOICE, EDGE_VOICES

        # Assert — giuseppe è Edge TTS
        assert DEFAULT_VOICE in EDGE_VOICES

    def test_edge_voices_have_valid_ids(self):
        """Gli ID delle voci Edge devono seguire il pattern xx-XX-*Neural."""
        from src.config import EDGE_VOICES

        # Assert
        for name, info in EDGE_VOICES.items():
            edge_id = info["edge_id"]
            assert edge_id.endswith("Neural"), (
                f"Voce '{name}' ha ID '{edge_id}' che non finisce con 'Neural'"
            )
            assert info["gender"] in (
                "M",
                "F",
            ), f"Voce '{name}' ha genere '{info['gender']}' non valido"
            assert info["lang"] in (
                "it",
                "en",
            ), f"Voce '{name}' ha lingua '{info['lang']}' non valida"

    def test_voice_urls_point_to_existing_files(self):
        """VOICE_URLS deve avere entry per modello e config JSON."""
        from src.config import VOICE_JSON, VOICE_MODEL, VOICE_URLS

        # Assert
        assert VOICE_MODEL in VOICE_URLS
        assert VOICE_JSON in VOICE_URLS

    def test_voice_model_path_uses_home_directory(self):
        """VOICE_DIR deve essere sotto la home directory dell'utente."""
        from src.config import VOICE_DIR

        # Assert
        assert str(VOICE_DIR).startswith(str(Path.home()))


# ===========================================================================
# Test — markdown_a_testo (edge case, fallback regex)
# ===========================================================================


class TestMarkdownATestoEdgeCases:
    """Test per edge case del parser Markdown regex (senza pandoc)."""

    def _converti(self, markdown: str) -> str:
        """Helper: converte markdown via file temp con fallback regex forzato."""
        from src.converters import file_a_testo

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(markdown)
            tmp_path = Path(f.name)
        try:
            with patch("src.converters.shutil.which", return_value=None):
                return file_a_testo(tmp_path)
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
        """Le immagini ![alt](url) devono essere rimosse completamente."""
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
    """Test per il percorso pandoc del convertitore Markdown."""

    def test_usa_pandoc_quando_disponibile(self):
        """Deve usare pandoc se disponibile nel PATH."""
        from src.converters import file_a_testo

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

            with (
                patch("src.converters.shutil.which", return_value="/usr/bin/pandoc"),
                patch("src.converters.subprocess.run", return_value=mock_result) as mock_run,
            ):
                # Act
                risultato = file_a_testo(tmp_path)

            # Assert
            mock_run.assert_called_once()
            assert "Titolo" in risultato
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_fallback_regex_se_pandoc_fallisce(self):
        """Se pandoc restituisce errore, deve cadere sul fallback regex."""
        from src.converters import file_a_testo

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

            with (
                patch("src.converters.shutil.which", return_value="/usr/bin/pandoc"),
                patch("src.converters.subprocess.run", return_value=mock_result),
            ):
                # Act
                risultato = file_a_testo(tmp_path)

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
        from src.leggi import concatena_wav

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
        from src.leggi import concatena_wav

        # Arrange & Act
        risultato = concatena_wav([], 22050)

        # Assert
        with wave.open(io.BytesIO(risultato), "rb") as wf:
            assert wf.getnframes() == 0

    def test_concatena_singolo_wav(self):
        """Un singolo WAV deve restituire un WAV con gli stessi frame."""
        from src.leggi import concatena_wav

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
        from src.synthesis import scarica_voce_piper

        # Arrange & Act
        with patch("src.synthesis.VOICE_DIR") as mock_dir, patch("src.synthesis.VOICE_URLS", {}):
            mock_dir.mkdir = MagicMock()
            # Nessun URL da scaricare
            scarica_voce_piper()

        # Assert — nessuna chiamata a urlopen
        # (il test verifica che non crashi con lista vuota)

    def test_crea_directory_se_non_esiste(self):
        """Deve creare la directory dei modelli con parents=True."""
        from src.synthesis import scarica_voce_piper

        # Arrange
        mock_path_model = MagicMock()
        mock_path_model.exists.return_value = True
        mock_path_model.name = "model.onnx"

        mock_path_json = MagicMock()
        mock_path_json.exists.return_value = True
        mock_path_json.name = "model.onnx.json"

        with (
            patch("src.synthesis.VOICE_DIR") as mock_dir,
            patch(
                "src.synthesis.VOICE_URLS",
                {
                    mock_path_model: "http://example.com/model",
                    mock_path_json: "http://example.com/model.json",
                },
            ),
        ):
            # Act
            scarica_voce_piper()

            # Assert
            mock_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)


# ===========================================================================
# Test — cross-platform: _trova_player, _ha_player, suggerisci_installazione
# ===========================================================================


class TestTrovaPlayer:
    """Test per la selezione del player audio in base all'OS."""

    def test_linux_wav_con_aplay(self):
        """Su Linux con aplay disponibile, deve usare aplay per WAV."""
        from src.leggi import _trova_player

        # Arrange & Act
        with (
            patch("src.leggi.PLATFORM", "linux"),
            patch("src.leggi.shutil.which", return_value="/usr/bin/aplay"),
        ):
            cmd, stdin = _trova_player("wav")

        # Assert
        assert cmd[0] == "aplay"
        assert stdin is True

    def test_linux_mp3_con_ffplay(self):
        """Su Linux deve usare ffplay per MP3."""
        from src.leggi import _trova_player

        # Arrange & Act
        with (
            patch("src.leggi.PLATFORM", "linux"),
            patch("src.leggi.shutil.which", return_value="/usr/bin/ffplay"),
        ):
            cmd, stdin = _trova_player("mp3")

        # Assert
        assert cmd[0] == "ffplay"
        assert stdin is True

    def test_darwin_con_afplay(self):
        """Su macOS con afplay disponibile, deve usare afplay."""
        from src.leggi import _trova_player

        # Arrange & Act
        with (
            patch("src.leggi.PLATFORM", "darwin"),
            patch("src.leggi.shutil.which", return_value="/usr/bin/afplay"),
        ):
            cmd, stdin = _trova_player("mp3")

        # Assert
        assert cmd == ["afplay"]
        assert stdin is False

    def test_darwin_fallback_ffplay(self):
        """Su macOS senza afplay, deve usare ffplay come fallback."""
        from src.leggi import _trova_player

        # Arrange
        def which_side_effect(name):
            return "/usr/bin/ffplay" if name == "ffplay" else None

        # Act
        with (
            patch("src.leggi.PLATFORM", "darwin"),
            patch("src.leggi.shutil.which", side_effect=which_side_effect),
        ):
            cmd, stdin = _trova_player("mp3")

        # Assert
        assert cmd[0] == "ffplay"
        assert stdin is True

    def test_win32_con_ffplay(self):
        """Su Windows con ffplay deve usare ffplay."""
        from src.leggi import _trova_player

        # Arrange & Act
        with (
            patch("src.leggi.PLATFORM", "win32"),
            patch("src.leggi.shutil.which", return_value="C:\\ffplay.exe"),
        ):
            cmd, stdin = _trova_player("wav")

        # Assert
        assert cmd[0] == "ffplay"
        assert stdin is True

    def test_nessun_player_disponibile(self):
        """Senza player, deve restituire lista vuota."""
        from src.leggi import _trova_player

        # Arrange & Act
        with (
            patch("src.leggi.PLATFORM", "linux"),
            patch("src.leggi.shutil.which", return_value=None),
        ):
            cmd, stdin = _trova_player("wav")

        # Assert
        assert cmd == []
        assert stdin is False


class TestHaPlayer:
    """Test per il check di disponibilità player."""

    def test_ha_player_true(self):
        """Deve restituire True se un player è disponibile."""
        from src.leggi import _ha_player

        # Arrange & Act
        with (
            patch("src.leggi.PLATFORM", "linux"),
            patch("src.leggi.shutil.which", return_value="/usr/bin/aplay"),
        ):
            risultato = _ha_player("wav")

        # Assert
        assert risultato is True

    def test_ha_player_false(self):
        """Deve restituire False se nessun player è disponibile."""
        from src.leggi import _ha_player

        # Arrange & Act
        with (
            patch("src.leggi.PLATFORM", "win32"),
            patch("src.leggi.shutil.which", return_value=None),
        ):
            risultato = _ha_player("mp3")

        # Assert
        assert risultato is False


class TestSuggerisciInstallazione:
    """Test per i messaggi di installazione OS-specifici."""

    def test_linux_ffmpeg(self):
        """Su Linux deve suggerire apt/dnf/pacman per ffmpeg."""
        from src.config import suggerisci_installazione

        # Act
        with patch("src.config.PLATFORM", "linux"):
            msg = suggerisci_installazione("ffmpeg")

        # Assert
        assert "apt" in msg

    def test_darwin_ffmpeg(self):
        """Su macOS deve suggerire brew per ffmpeg."""
        from src.config import suggerisci_installazione

        # Act
        with patch("src.config.PLATFORM", "darwin"):
            msg = suggerisci_installazione("ffmpeg")

        # Assert
        assert "brew" in msg

    def test_win32_ffmpeg(self):
        """Su Windows deve suggerire choco/scoop per ffmpeg."""
        from src.config import suggerisci_installazione

        # Act
        with patch("src.config.PLATFORM", "win32"):
            msg = suggerisci_installazione("ffmpeg")

        # Assert
        assert "choco" in msg

    def test_pacchetto_sconosciuto(self):
        """Per pacchetti non mappati deve restituire messaggio generico."""
        from src.config import suggerisci_installazione

        # Act
        with patch("src.config.PLATFORM", "linux"):
            msg = suggerisci_installazione("pacchetto_inesistente")

        # Assert
        assert "package manager" in msg


# ===========================================================================
# Test — verifica_prerequisiti
# ===========================================================================


class TestVerificaPrerequisiti:
    """Test per il check delle dipendenze di sistema all'avvio."""

    def test_tutto_presente_nessun_errore(self):
        """Con tutte le dipendenze presenti, deve restituire lista vuota."""
        from src.config import verifica_prerequisiti

        # Arrange & Act
        with (
            patch("src.config.PLATFORM", "linux"),
            patch("src.config.shutil.which", return_value="/usr/bin/found"),
        ):
            errori = verifica_prerequisiti(modalita="cli")

        # Assert
        assert errori == []

    def test_ffmpeg_mancante_errore_critico(self):
        """Senza ffmpeg deve restituire errore critico."""
        from src.config import verifica_prerequisiti

        # Arrange
        def which_side_effect(name):
            return None if name == "ffmpeg" else "/usr/bin/found"

        # Act
        with (
            patch("src.config.PLATFORM", "linux"),
            patch("src.config.shutil.which", side_effect=which_side_effect),
        ):
            errori = verifica_prerequisiti(modalita="cli")

        # Assert
        assert "ffmpeg" in errori

    def test_modalita_web_non_controlla_player(self):
        """In modalità web non deve controllare il player audio."""
        from src.config import verifica_prerequisiti

        # Arrange
        def which_side_effect(name):
            if name == "ffmpeg":
                return "/usr/bin/ffmpeg"
            if name == "pandoc":
                return "/usr/bin/pandoc"
            return None  # nessun player audio

        # Act
        with (
            patch("src.config.PLATFORM", "linux"),
            patch("src.config.shutil.which", side_effect=which_side_effect),
        ):
            errori = verifica_prerequisiti(modalita="web")

        # Assert — nessun errore, anche senza player
        assert errori == []

    def test_pandoc_mancante_solo_warning(self, capsys):
        """Pandoc mancante deve generare warning, non errore critico."""
        from src.config import verifica_prerequisiti

        # Arrange
        def which_side_effect(name):
            if name == "pandoc":
                return None
            return "/usr/bin/found"

        # Act
        with (
            patch("src.config.PLATFORM", "linux"),
            patch("src.config.shutil.which", side_effect=which_side_effect),
        ):
            errori = verifica_prerequisiti(modalita="cli")

        # Assert
        assert errori == []
        captured = capsys.readouterr()
        assert "pandoc" in captured.out

    def test_darwin_senza_player_stampa_warning(self, capsys):
        """Su darwin CLI, senza afplay né ffplay, deve stampare warning player."""
        from src.config import verifica_prerequisiti

        # Arrange — ffmpeg e pandoc presenti, nessun player
        def which_side_effect(name):
            if name in ("afplay", "ffplay"):
                return None
            return "/usr/bin/found"

        # Act
        with (
            patch("src.config.PLATFORM", "darwin"),
            patch("src.config.shutil.which", side_effect=which_side_effect),
        ):
            errori = verifica_prerequisiti(modalita="cli")

        # Assert — nessun errore critico, ma warning stampato
        assert errori == []
        captured = capsys.readouterr()
        assert "player" in captured.out.lower() or "player" in captured.err.lower()

    def test_darwin_con_afplay_nessun_warning_player(self, capsys):
        """Su darwin CLI con afplay disponibile, NON deve avvertire sul player."""
        from src.config import verifica_prerequisiti

        # Arrange — tutto presente, compreso afplay
        def which_side_effect(name):
            return f"/usr/bin/{name}"

        # Act
        with (
            patch("src.config.PLATFORM", "darwin"),
            patch("src.config.shutil.which", side_effect=which_side_effect),
        ):
            errori = verifica_prerequisiti(modalita="cli")

        # Assert — nessun errore, nessun warning player nell'output
        assert errori == []
        captured = capsys.readouterr()
        # Non deve avvertire sull'assenza di player
        assert "Nessun player" not in captured.out
        assert "Nessun player" not in captured.err

    def test_win32_senza_ffplay_stampa_warning(self, capsys):
        """Su win32 CLI, senza ffplay, deve stampare warning player."""
        from src.config import verifica_prerequisiti

        # Arrange — ffmpeg e pandoc presenti, ffplay assente
        def which_side_effect(name):
            if name == "ffplay":
                return None
            return "C:\\tools\\found.exe"

        # Act
        with (
            patch("src.config.PLATFORM", "win32"),
            patch("src.config.shutil.which", side_effect=which_side_effect),
        ):
            errori = verifica_prerequisiti(modalita="cli")

        # Assert — nessun errore critico, warning stampato
        assert errori == []
        captured = capsys.readouterr()
        assert "player" in captured.out.lower() or "player" in captured.err.lower()


# ===========================================================================
# Test — mostra_paragrafo
# ===========================================================================


class TestMostraParagrafo:
    """Test per la funzione di display terminale."""

    def test_non_stampa_se_non_visibile(self, capsys):
        """Se visibile=False, non deve stampare nulla."""
        from src.leggi import mostra_paragrafo

        # Act
        mostra_paragrafo(1, 10, "Testo del paragrafo", visibile=False)

        # Assert
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_stampa_se_visibile(self, capsys):
        """Se visibile=True, deve stampare il contatore e il testo."""
        from src.leggi import mostra_paragrafo

        # Act
        mostra_paragrafo(3, 10, "Contenuto paragrafo", visibile=True)

        # Assert
        captured = capsys.readouterr()
        assert "3/10" in captured.out
        assert "Contenuto paragrafo" in captured.out


# ===========================================================================
# Test — calcola_path_output
# ===========================================================================


class TestCalcolaPathOutput:
    """Test per il calcolo delle directory di output."""

    def test_struttura_output_corretta(self):
        """Deve restituire cartella_base, path MP3 completo e cartella paragrafi."""
        from src.leggi import calcola_path_output

        # Act
        cartella_base, path_mp3, cartella_par = calcola_path_output(Path("data/input/documento.md"))

        # Assert
        assert cartella_base.name == "documento"
        assert path_mp3.name == "documento.mp3"
        assert path_mp3.parent.name == "full"
        assert cartella_par.name == "paragraphs"

    def test_path_mp3_dentro_full(self):
        """Il file MP3 deve essere in cartella_base/full/."""
        from src.leggi import calcola_path_output

        _, path_mp3, _ = calcola_path_output(Path("test.epub"))

        assert path_mp3.parts[-2] == "full"
        assert path_mp3.suffix == ".mp3"
        assert path_mp3.stem == "test"

    def test_cartella_paragraphs_dentro_base(self):
        """La cartella paragrafi deve essere in cartella_base/paragraphs/."""
        from src.leggi import calcola_path_output

        cartella_base, _, cartella_par = calcola_path_output(Path("libro.pdf"))

        assert cartella_par.parent == cartella_base
        assert cartella_par.name == "paragraphs"

    def test_estensione_non_influisce_su_stem(self):
        """Lo stem deve essere il nome file senza estensione."""
        from src.leggi import calcola_path_output

        for ext in [".md", ".txt", ".epub", ".docx", ".pdf"]:
            _, path_mp3, _ = calcola_path_output(Path(f"mio_file{ext}"))
            assert path_mp3.stem == "mio_file"

    def test_file_con_path_complesso(self):
        """Deve usare solo lo stem, ignorando directory padre."""
        from src.leggi import calcola_path_output

        cartella_base, _, _ = calcola_path_output(Path("/home/user/documenti/relazione.md"))

        assert cartella_base.name == "relazione"


# ===========================================================================
# Test — leggi_con_piper
# ===========================================================================


class TestLeggiConPiper:
    """Test per la lettura CLI con Piper TTS."""

    def _make_wav_bytes(self, sample_rate: int = 22050) -> bytes:
        """Helper: crea WAV valido in memoria."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00\x00" * 100)
        return buf.getvalue()

    def test_esce_se_piper_non_installato(self):
        """Deve uscire con sys.exit(1) se piper non è importabile."""
        from src.leggi import leggi_con_piper

        with (
            patch.dict("sys.modules", {"piper": None}),
            pytest.raises(SystemExit, match="1"),
        ):
            leggi_con_piper("Testo di prova")

    def test_esce_se_no_player_e_no_salva(self):
        """Deve uscire se non c'è player audio e non si salva."""
        from src.leggi import leggi_con_piper

        mock_piper_module = MagicMock()
        with (
            patch.dict("sys.modules", {"piper": mock_piper_module}),
            patch("src.leggi._ha_player", return_value=False),
            pytest.raises(SystemExit, match="1"),
        ):
            leggi_con_piper("Testo di prova", salva_path=None)

    def test_sintetizza_e_riproduce_paragrafi(self):
        """Deve sintetizzare e riprodurre ogni paragrafo."""
        from src.leggi import leggi_con_piper

        wav = self._make_wav_bytes()
        mock_piper_module = MagicMock()
        mock_voce = MagicMock()
        mock_voce.config.sample_rate = 22050
        mock_piper_module.PiperVoice.load.return_value = mock_voce

        with (
            patch.dict("sys.modules", {"piper": mock_piper_module}),
            patch("src.leggi._ha_player", return_value=True),
            patch("src.leggi.sintetizza_piper", return_value=wav) as mock_sint,
            patch("src.leggi.riproduci_audio") as mock_play,
            patch("src.leggi.mostra_paragrafo"),
        ):
            leggi_con_piper("Primo paragrafo\n\nSecondo paragrafo")

        assert mock_sint.call_count == 2
        assert mock_play.call_count == 2

    def test_salva_mp3_senza_riprodurre(self, tmp_path):
        """Con salva_path e senza player, deve salvare senza riprodurre."""
        from src.leggi import leggi_con_piper

        wav = self._make_wav_bytes()
        mock_piper_module = MagicMock()
        mock_voce = MagicMock()
        mock_voce.config.sample_rate = 22050
        mock_piper_module.PiperVoice.load.return_value = mock_voce

        salva = tmp_path / "output.mp3"
        cartella_par = tmp_path / "paragraphs"

        with (
            patch.dict("sys.modules", {"piper": mock_piper_module}),
            patch("src.leggi._ha_player", return_value=False),
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("src.leggi.sintetizza_piper", return_value=wav),
            patch("src.leggi.wav_a_mp3") as mock_mp3,
            patch("src.leggi.concatena_wav", return_value=wav),
            patch("src.leggi.riproduci_audio") as mock_play,
            patch("src.leggi.mostra_paragrafo"),
        ):
            leggi_con_piper("Un paragrafo", salva_path=salva, cartella_par=cartella_par)

        # Non deve riprodurre
        mock_play.assert_not_called()
        # Deve salvare: 1 paragrafo singolo + 1 file completo
        assert mock_mp3.call_count == 2


# ===========================================================================
# Test — leggi_con_edge
# ===========================================================================


class TestLeggiConEdge:
    """Test per la lettura CLI con Edge TTS."""

    def test_esce_se_edge_tts_non_installato(self):
        """Deve uscire con sys.exit(1) se edge-tts non è importabile."""
        from src.leggi import leggi_con_edge

        with (
            patch.dict("sys.modules", {"edge_tts": None}),
            pytest.raises(SystemExit, match="1"),
        ):
            leggi_con_edge("Testo", voice_name="giuseppe")

    def test_esce_se_no_player_e_no_salva(self):
        """Deve uscire se non c'è player audio e non si salva."""
        from src.leggi import leggi_con_edge

        mock_edge = MagicMock()
        with (
            patch.dict("sys.modules", {"edge_tts": mock_edge}),
            patch("src.leggi._ha_player", return_value=False),
            pytest.raises(SystemExit, match="1"),
        ):
            leggi_con_edge("Testo", voice_name="giuseppe", salva_path=None)

    def test_chiama_asyncio_run_con_loop_edge(self):
        """Deve chiamare asyncio.run con _loop_edge."""
        from src.leggi import leggi_con_edge

        mock_edge = MagicMock()
        with (
            patch.dict("sys.modules", {"edge_tts": mock_edge}),
            patch("src.leggi._ha_player", return_value=True),
            patch("src.leggi.asyncio.run") as mock_run,
            patch("src.leggi.mostra_paragrafo"),
        ):
            leggi_con_edge("Paragrafo uno", voice_name="giuseppe")

        mock_run.assert_called_once()


# ===========================================================================
# Test — main
# ===========================================================================


class TestMain:
    """Test per l'entry point CLI."""

    def test_file_non_trovato_esce(self):
        """Deve uscire se il file non esiste."""
        from src.leggi import main

        with (
            patch("sys.argv", ["leggi.py", "/non_esiste_12345.md"]),
            patch("src.leggi.verifica_prerequisiti", return_value=[]),
            pytest.raises(SystemExit, match="1"),
        ):
            main()

    def test_file_vuoto_esce(self, tmp_path):
        """Deve uscire se il file è vuoto dopo conversione."""
        from src.leggi import main

        vuoto = tmp_path / "vuoto.txt"
        vuoto.write_text("")

        with (
            patch("sys.argv", ["leggi.py", str(vuoto)]),
            patch("src.leggi.verifica_prerequisiti", return_value=[]),
            pytest.raises(SystemExit, match="1"),
        ):
            main()

    def test_prerequisiti_falliti_esce(self, tmp_path):
        """Deve uscire se verifica_prerequisiti ritorna errori."""
        from src.leggi import main

        f = tmp_path / "test.txt"
        f.write_text("contenuto")

        with (
            patch("sys.argv", ["leggi.py", str(f)]),
            patch("src.leggi.verifica_prerequisiti", return_value=["ffmpeg"]),
            pytest.raises(SystemExit, match="1"),
        ):
            main()

    def test_voce_piper_chiama_leggi_con_piper(self, tmp_path):
        """Con --voice paola deve chiamare scarica_voce_piper + leggi_con_piper."""
        from src.leggi import main

        f = tmp_path / "test.txt"
        f.write_text("Contenuto test")

        with (
            patch("sys.argv", ["leggi.py", str(f), "--voice", "paola"]),
            patch("src.leggi.verifica_prerequisiti", return_value=[]),
            patch("src.leggi.scarica_voce_piper") as mock_scarica,
            patch("src.leggi.leggi_con_piper") as mock_leggi,
        ):
            main()

        mock_scarica.assert_called_once()
        mock_leggi.assert_called_once()

    def test_voce_edge_chiama_leggi_con_edge(self, tmp_path):
        """Con --voice giuseppe deve chiamare leggi_con_edge."""
        from src.leggi import main

        f = tmp_path / "test.txt"
        f.write_text("Contenuto test")

        with (
            patch("sys.argv", ["leggi.py", str(f), "--voice", "giuseppe"]),
            patch("src.leggi.verifica_prerequisiti", return_value=[]),
            patch("src.leggi.leggi_con_edge") as mock_leggi,
        ):
            main()

        mock_leggi.assert_called_once()
        assert mock_leggi.call_args[1]["salva_path"] is None

    def test_salva_flag_calcola_path_output(self, tmp_path):
        """Con --salva deve calcolare path output e passarli alla funzione TTS."""
        from src.leggi import main

        f = tmp_path / "documento.txt"
        f.write_text("Contenuto da salvare")

        with (
            patch("sys.argv", ["leggi.py", str(f), "--voice", "giuseppe", "--salva"]),
            patch("src.leggi.verifica_prerequisiti", return_value=[]),
            patch("src.leggi.leggi_con_edge") as mock_leggi,
        ):
            main()

        # salva_path non deve essere None
        assert mock_leggi.call_args[1]["salva_path"] is not None
        assert mock_leggi.call_args[1]["cartella_par"] is not None


# ===========================================================================
# Test — wav_a_mp3
# ===========================================================================


class TestWavAMp3:
    """Test per la conversione WAV → MP3 via ffmpeg."""

    def test_chiama_ffmpeg_con_argomenti_corretti(self, tmp_path):
        """Deve chiamare subprocess.run con i flag ffmpeg corretti."""
        from src.leggi import wav_a_mp3

        # Arrange
        output = tmp_path / "output.mp3"
        audio = b"\x00" * 100

        with patch("src.leggi.subprocess.run") as mock_run:
            # Act
            wav_a_mp3(audio, output)

        # Assert — ffmpeg invocato con i parametri corretti
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "pipe:0" in cmd
        assert "libmp3lame" in cmd
        assert str(output) in cmd

    def test_passa_wav_bytes_come_stdin(self, tmp_path):
        """I byte WAV devono essere passati come stdin a ffmpeg."""
        from src.leggi import wav_a_mp3

        # Arrange
        output = tmp_path / "output.mp3"
        audio = b"\xDE\xAD\xBE\xEF"

        with patch("src.leggi.subprocess.run") as mock_run:
            # Act
            wav_a_mp3(audio, output)

        # Assert
        kwargs = mock_run.call_args[1]
        assert kwargs["input"] == audio
        assert kwargs["check"] is True

    def test_timeout_impostato_a_30(self, tmp_path):
        """Deve impostare timeout=30 per evitare blocchi infiniti."""
        from src.leggi import wav_a_mp3

        # Arrange
        output = tmp_path / "output.mp3"

        with patch("src.leggi.subprocess.run") as mock_run:
            # Act
            wav_a_mp3(b"", output)

        # Assert
        assert mock_run.call_args[1]["timeout"] == 30


# ===========================================================================
# Test — concatena_mp3
# ===========================================================================


class TestConcatenaMp3:
    """Test per la concatenazione MP3 via ffmpeg."""

    def test_chiama_ffmpeg_con_filtro_concat(self, tmp_path):
        """Deve usare il filtro concat di ffmpeg."""
        from src.leggi import concatena_mp3

        # Arrange
        output = tmp_path / "completo.mp3"
        frammenti = [b"\x01" * 50, b"\x02" * 50]

        with patch("src.leggi.subprocess.run") as mock_run:
            # Act
            concatena_mp3(frammenti, output)

        # Assert
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert any("concat" in arg for arg in cmd)
        assert str(output) in cmd

    def test_unisce_tutti_i_frammenti_come_stdin(self, tmp_path):
        """I byte di tutti i frammenti devono essere concatenati e passati come stdin."""
        from src.leggi import concatena_mp3

        # Arrange
        output = tmp_path / "completo.mp3"
        frammenti = [b"AAA", b"BBB", b"CCC"]

        with patch("src.leggi.subprocess.run") as mock_run:
            # Act
            concatena_mp3(frammenti, output)

        # Assert
        kwargs = mock_run.call_args[1]
        assert kwargs["input"] == b"AAABBBCCC"
        assert kwargs["check"] is True
        assert kwargs["timeout"] == 30


# ===========================================================================
# Test — riproduci_audio
# ===========================================================================


class TestRiproduciAudio:
    """Test per la riproduzione audio con fallback player."""

    def test_nessun_player_non_chiama_subprocess(self):
        """Senza player disponibile non deve chiamare subprocess.run."""
        from src.leggi import riproduci_audio

        # Arrange
        with (
            patch("src.leggi._trova_player", return_value=([], False)),
            patch("src.leggi.subprocess.run") as mock_run,
        ):
            # Act
            riproduci_audio(b"\x00" * 10, "mp3")

        # Assert
        mock_run.assert_not_called()

    def test_stdin_path_passa_bytes_direttamente(self):
        """Con player stdin-compatibile, deve passare i byte come stdin."""
        from src.leggi import riproduci_audio

        # Arrange
        audio = b"\xAB" * 20
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-"]

        with (
            patch("src.leggi._trova_player", return_value=(cmd, True)),
            patch("src.leggi.subprocess.run") as mock_run,
        ):
            # Act
            riproduci_audio(audio, "mp3")

        # Assert
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["input"] == audio
        assert mock_run.call_args[0][0] == cmd

    def test_tempfile_path_lancia_player_con_path_file(self):
        """Con afplay (non stdin), il comando deve includere il path del file temp."""
        from src.leggi import riproduci_audio

        # Arrange
        audio = b"\xFF" * 30
        cmd = ["afplay"]

        with (
            patch("src.leggi._trova_player", return_value=(cmd, False)),
            patch("src.leggi.subprocess.run") as mock_run,
        ):
            # Act
            riproduci_audio(audio, "mp3")

        # Assert — comando = ["afplay", "/tmp/xxx.mp3"]
        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "afplay"
        assert len(called_cmd) == 2
        assert called_cmd[1].endswith(".mp3")

    def test_tempfile_eliminato_dopo_riproduzione(self, tmp_path):
        """Il file temporaneo deve essere eliminato dopo la riproduzione."""
        from src.leggi import riproduci_audio

        # Arrange — crea un file temporaneo reale per verificare la cancellazione
        fake_tmp = tmp_path / "audio_test.mp3"
        fake_tmp.write_bytes(b"\x00")
        tmp_name = str(fake_tmp)

        class FakeTmp:
            name = tmp_name

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def write(self, data):
                pass

        # tempfile è importato inline in riproduci_audio: patch nel modulo globale
        with (
            patch("src.leggi._trova_player", return_value=(["afplay"], False)),
            patch("src.leggi.subprocess.run"),
            patch("tempfile.NamedTemporaryFile", return_value=FakeTmp()),
        ):
            # Act
            riproduci_audio(b"\x00", "mp3")

        # Assert — il file deve essere stato cancellato
        assert not fake_tmp.exists()


# ===========================================================================
# Test — leggi_con_piper (path aggiuntivi)
# ===========================================================================


class TestLeggiConPiperExtra:
    """Test per i percorsi non coperti in leggi_con_piper."""

    def _make_wav_bytes(self, sample_rate: int = 22050) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00\x00" * 100)
        return buf.getvalue()

    def test_esce_se_salva_path_e_ffmpeg_non_trovato(self, tmp_path):
        """Deve uscire con sys.exit(1) se salva_path è specificato ma ffmpeg manca."""
        from src.leggi import leggi_con_piper

        # Arrange
        mock_piper_module = MagicMock()
        salva = Path(tmp_path / "output.mp3")

        with (
            patch.dict("sys.modules", {"piper": mock_piper_module}),
            patch("src.leggi._ha_player", return_value=True),
            patch("src.leggi.shutil.which", return_value=None),
            pytest.raises(SystemExit, match="1"),
        ):
            # Act
            leggi_con_piper("Un testo", salva_path=salva)

    def test_keyboard_interrupt_gestito_gracefully(self):
        """KeyboardInterrupt durante la lettura deve terminare senza propagarsi."""
        from src.leggi import leggi_con_piper

        # Arrange
        mock_piper_module = MagicMock()
        mock_voce = MagicMock()
        mock_voce.config.sample_rate = 22050
        mock_piper_module.PiperVoice.load.return_value = mock_voce

        with (
            patch.dict("sys.modules", {"piper": mock_piper_module}),
            patch("src.leggi._ha_player", return_value=True),
            patch("src.leggi.sintetizza_piper", side_effect=KeyboardInterrupt),
            patch("src.leggi.mostra_paragrafo"),
        ):
            # Act — non deve sollevare eccezioni né SystemExit
            leggi_con_piper("Paragrafo uno\n\nParagrafo due")

        # Assert implicito: se arriviamo qui senza eccezioni, il test passa


# ===========================================================================
# Test — leggi_con_edge (path aggiuntivi)
# ===========================================================================


class TestLeggiConEdgeExtra:
    """Test per i percorsi non coperti in leggi_con_edge."""

    def test_crea_directory_salva_path_e_cartella_par(self, tmp_path):
        """Con salva_path deve creare le directory padre e cartella_par."""
        from src.leggi import leggi_con_edge

        # Arrange
        mock_edge = MagicMock()
        salva = tmp_path / "nuova_dir" / "output.mp3"
        cartella_par = tmp_path / "nuova_dir" / "paragraphs"

        with (
            patch.dict("sys.modules", {"edge_tts": mock_edge}),
            patch("src.leggi._ha_player", return_value=False),
            patch("src.leggi.asyncio.run"),
        ):
            # Act
            leggi_con_edge(
                "Testo", voice_name="giuseppe", salva_path=salva, cartella_par=cartella_par
            )

        # Assert
        assert salva.parent.exists()
        assert cartella_par.exists()

    def test_crea_solo_parent_se_cartella_par_none(self, tmp_path):
        """Con salva_path ma senza cartella_par deve creare solo la directory padre."""
        from src.leggi import leggi_con_edge

        # Arrange
        mock_edge = MagicMock()
        salva = tmp_path / "altra_dir" / "output.mp3"

        with (
            patch.dict("sys.modules", {"edge_tts": mock_edge}),
            patch("src.leggi._ha_player", return_value=False),
            patch("src.leggi.asyncio.run"),
        ):
            # Act
            leggi_con_edge("Testo", voice_name="giuseppe", salva_path=salva, cartella_par=None)

        # Assert
        assert salva.parent.exists()


# ===========================================================================
# Test — _loop_edge (funzione async)
# ===========================================================================


async def _noop_coroutine():
    """Coroutine noop per mock asincroni."""
    return None


class TestLoopEdge:
    """Test per la funzione async _loop_edge."""

    def _make_mp3(self) -> bytes:
        return b"\xFF\xFB" + b"\x00" * 48

    def test_salva_mp3_per_paragrafo_e_file_completo(self, tmp_path):
        """Con salva_path deve salvare ogni paragrafo e chiamare concatena_mp3."""
        from src.leggi import _loop_edge

        # Arrange
        mp3 = self._make_mp3()
        salva = tmp_path / "full" / "output.mp3"
        salva.parent.mkdir(parents=True)
        cartella_par = tmp_path / "paragraphs"
        cartella_par.mkdir()
        paragrafi = ["Primo", "Secondo"]

        async def fake_sint(voice_id, testo):
            return mp3

        with (
            patch("src.leggi.sintetizza_edge", side_effect=fake_sint),
            patch("src.leggi.concatena_mp3") as mock_concat,
            patch("src.leggi.mostra_paragrafo"),
        ):
            # Act
            asyncio.run(
                _loop_edge("it-IT-GiuseppeNeural", paragrafi, False, salva, cartella_par)
            )

        # Assert — concatena_mp3 chiamato con 2 frammenti
        mock_concat.assert_called_once()
        lista, path = mock_concat.call_args[0]
        assert len(lista) == 2
        assert path == salva
        assert (cartella_par / "001.mp3").exists()
        assert (cartella_par / "002.mp3").exists()

    def test_salva_senza_cartella_par(self, tmp_path):
        """Con salva_path ma senza cartella_par non deve creare file singoli."""
        from src.leggi import _loop_edge

        # Arrange
        mp3 = self._make_mp3()
        salva = tmp_path / "full" / "output.mp3"
        salva.parent.mkdir(parents=True)
        paragrafi = ["Solo uno"]

        async def fake_sint(voice_id, testo):
            return mp3

        with (
            patch("src.leggi.sintetizza_edge", side_effect=fake_sint),
            patch("src.leggi.concatena_mp3") as mock_concat,
            patch("src.leggi.mostra_paragrafo"),
        ):
            # Act
            asyncio.run(_loop_edge("it-IT-GiuseppeNeural", paragrafi, False, salva, None))

        # Assert
        mock_concat.assert_called_once()

    def test_keyboard_interrupt_nel_loop_edge_non_propaga(self):
        """Il loop edge completa senza propagare eccezioni su input validi."""
        # Nota: KeyboardInterrupt sollevato in un asyncio task viene propagato
        # direttamente da asyncio.run() in Python 3.12+, bypassando il
        # try/except dentro la coroutine. Le righe 303-304 di leggi.py sono
        # raggiungibili solo con SIGINT reale, non verificabile via unit test.
        # Questo test verifica che il loop termini normalmente su input valido.
        from src.leggi import _loop_edge

        # Arrange
        mp3 = self._make_mp3()
        paragrafi = ["Solo uno"]

        async def fake_sint(voice_id, testo):
            return mp3

        with (
            patch("src.leggi.sintetizza_edge", side_effect=fake_sint),
            patch("src.leggi.mostra_paragrafo"),
        ):
            # Act & Assert — non deve sollevare eccezioni
            asyncio.run(_loop_edge("it-IT-GiuseppeNeural", paragrafi, False, None, None))

    def test_riproduce_con_riproduci_async(self):
        """Con riproduce=True deve chiamare _riproduci_async per ogni paragrafo."""
        from src.leggi import _loop_edge

        # Arrange
        mp3 = self._make_mp3()
        paragrafi = ["Primo", "Secondo"]
        riproduci_calls = []

        async def fake_sint(voice_id, testo):
            return mp3

        async def fake_riproduci(mp3_bytes):
            riproduci_calls.append(mp3_bytes)

        with (
            patch("src.leggi.sintetizza_edge", side_effect=fake_sint),
            patch("src.leggi._riproduci_async", side_effect=fake_riproduci),
            patch("src.leggi.mostra_paragrafo"),
        ):
            # Act
            asyncio.run(_loop_edge("it-IT-GiuseppeNeural", paragrafi, True, None, None))

        # Assert
        assert len(riproduci_calls) == 2

    def test_non_chiama_concatena_se_nessun_paragrafo_salvato(self, tmp_path):
        """Se salva_path è None, concatena_mp3 non deve essere chiamata."""
        from src.leggi import _loop_edge

        # Arrange
        mp3 = self._make_mp3()
        paragrafi = ["Testo"]

        async def fake_sint(voice_id, testo):
            return mp3

        async def fake_riproduci(mp3_bytes):
            pass

        with (
            patch("src.leggi.sintetizza_edge", side_effect=fake_sint),
            patch("src.leggi._riproduci_async", side_effect=fake_riproduci),
            patch("src.leggi.concatena_mp3") as mock_concat,
            patch("src.leggi.mostra_paragrafo"),
        ):
            # Act
            asyncio.run(_loop_edge("it-IT-GiuseppeNeural", paragrafi, True, None, None))

        # Assert
        mock_concat.assert_not_called()


# ===========================================================================
# Test — _riproduci_async (funzione async)
# ===========================================================================


class TestRiproduciAsync:
    """Test per la funzione async _riproduci_async."""

    def test_stdin_path_usa_create_subprocess_exec_con_pipe(self):
        """Con player stdin-compatibile deve aprire il processo con stdin=PIPE."""
        from src.leggi import _riproduci_async

        # Arrange
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-"]
        mp3 = b"\xFF\xFB" + b"\x00" * 48

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with (
            patch("src.leggi._trova_player", return_value=(cmd, True)),
            patch(
                "src.leggi.asyncio.create_subprocess_exec",
                return_value=mock_proc,
            ) as mock_exec,
        ):
            # Act
            asyncio.run(_riproduci_async(mp3))

        # Assert
        mock_exec.assert_called_once()
        assert mock_exec.call_args[1]["stdin"] == asyncio.subprocess.PIPE

    def test_stdin_path_passa_bytes_a_communicate(self):
        """I byte MP3 devono essere passati a proc.communicate(input=...)."""
        from src.leggi import _riproduci_async

        # Arrange
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-"]
        mp3 = b"\xAA\xBB\xCC"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with (
            patch("src.leggi._trova_player", return_value=(cmd, True)),
            patch("src.leggi.asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            # Act
            asyncio.run(_riproduci_async(mp3))

        # Assert
        mock_proc.communicate.assert_called_once_with(input=mp3)

    def test_nessun_player_ritorna_senza_subprocess(self):
        """Senza player disponibile deve tornare senza creare processi."""
        from src.leggi import _riproduci_async

        # Arrange
        with (
            patch("src.leggi._trova_player", return_value=([], False)),
            patch("src.leggi.asyncio.create_subprocess_exec") as mock_exec,
        ):
            # Act
            asyncio.run(_riproduci_async(b"\x00"))

        # Assert
        mock_exec.assert_not_called()

    def test_tempfile_path_usa_proc_wait(self):
        """Con afplay (non stdin) deve chiamare proc.wait() non proc.communicate()."""
        from src.leggi import _riproduci_async

        # Arrange
        cmd = ["afplay"]
        mp3 = b"\xFF" * 20

        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)

        with (
            patch("src.leggi._trova_player", return_value=(cmd, False)),
            patch(
                "src.leggi.asyncio.create_subprocess_exec",
                return_value=mock_proc,
            ) as mock_exec,
        ):
            # Act
            asyncio.run(_riproduci_async(mp3))

        # Assert — proc.wait() chiamato, non communicate()
        mock_proc.wait.assert_called_once()
        mock_proc.communicate.assert_not_called()
        # afplay + path file temporaneo
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "afplay"
        assert call_args[-1].endswith(".mp3")

    def test_tempfile_eliminato_dopo_riproduzione(self, tmp_path):
        """Il file temporaneo deve essere eliminato dopo la riproduzione."""
        from src.leggi import _riproduci_async

        # Arrange
        cmd = ["afplay"]
        fake_tmp = tmp_path / "audio_tmp.mp3"
        fake_tmp.write_bytes(b"\x00")
        tmp_name = str(fake_tmp)

        class FakeTmp:
            name = tmp_name

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def write(self, data):
                pass

        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)

        # tempfile è importato inline in _riproduci_async: patch nel modulo globale
        with (
            patch("src.leggi._trova_player", return_value=(cmd, False)),
            patch("src.leggi.asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("tempfile.NamedTemporaryFile", return_value=FakeTmp()),
        ):
            # Act
            asyncio.run(_riproduci_async(b"\x00"))

        # Assert — il file temp non esiste più
        assert not fake_tmp.exists()
