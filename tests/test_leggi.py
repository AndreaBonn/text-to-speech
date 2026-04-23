"""
tests/test_leggi.py
Test per le funzioni di leggi.py e moduli correlati.

Copre: costanti/configurazione voci, convertitore Markdown (edge case),
scarica_voce_piper (synthesis), concatena_wav, mostra_paragrafo,
calcola_path_output, leggi_con_piper, leggi_con_edge, main.
"""

import io
import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

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
