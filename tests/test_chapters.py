"""
tests/test_chapters.py
Test per il modulo chapters.py: aggancio dei titoli ai paragrafi e capitoli ID3.

I test audio usano MP3 sintetici brevi generati con ffmpeg (sine), mai la rete.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from src.chapters import (
    ProbeError,
    aggiungi_capitoli_wav,
    inizi_capitoli,
    metadata_ffmetadata,
    timeline_mp3,
    trova_capitoli,
    unisci_con_capitoli,
)
from src.titles import Titolo


def _audio_md5(mp3: bytes, tmp_path: Path) -> str:
    """MD5 dei pacchetti audio (non dei tag): uguale solo se l'audio non è ricodificato."""
    path = tmp_path / "md5.mp3"
    path.write_bytes(mp3)
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a", "-c", "copy", "-f", "md5", "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


# ===========================================================================
# Test — trova_capitoli
# ===========================================================================


class TestTrovaCapitoli:
    def test_aggancia_i_titoli_in_ordine(self):
        paragrafi = ["Uno", "testo a", "Due", "testo b", "Tre", "testo c"]
        titoli = [Titolo("Uno", "Uno"), Titolo("Due", "Due"), Titolo("Tre", "Tre")]

        assert trova_capitoli(paragrafi, titoli) == [(0, "Uno"), (2, "Due"), (4, "Tre")]

    def test_senza_titoli_nessun_capitolo(self):
        assert trova_capitoli(["a", "b"], []) == []

    def test_confronto_ignora_spazi_e_maiuscole(self):
        paragrafi = ["intro", "CAPITOLO   primo\n", "testo"]
        titoli = [Titolo("Capitolo primo", "capitolo primo")]

        assert trova_capitoli(paragrafi, titoli) == [(0, "Capitolo primo")]

    def test_aggancio_sul_frammento_titolo_completo(self):
        """L'HTML spezza <h1>Ciao <em>mondo</em></h1>: si aggancia "Ciao", il titolo resta."""
        paragrafi = ["Ciao", "mondo", "testo"]
        titoli = [Titolo("Ciao mondo", "Ciao")]

        assert trova_capitoli(paragrafi, titoli) == [(0, "Ciao mondo")]

    def test_testo_prima_del_primo_titolo_parte_da_zero(self):
        paragrafi = ["premessa", "Uno", "testo", "Due"]
        titoli = [Titolo("Uno", "Uno"), Titolo("Due", "Due")]

        assert trova_capitoli(paragrafi, titoli) == [(0, "Uno"), (3, "Due")]

    def test_titolo_non_trovato_viene_saltato(self):
        paragrafi = ["Uno", "testo", "Tre"]
        titoli = [Titolo("Uno", "Uno"), Titolo("Due", "Due"), Titolo("Tre", "Tre")]

        assert trova_capitoli(paragrafi, titoli) == [(0, "Uno"), (2, "Tre")]

    def test_titolo_ripetuto_si_aggancia_dopo_il_precedente(self):
        """Un titolo uguale a un paragrafo già usato prende l'occorrenza successiva."""
        paragrafi = ["Note", "testo", "Note", "altro"]
        titoli = [Titolo("Note", "Note"), Titolo("Note", "Note")]

        assert trova_capitoli(paragrafi, titoli) == [(0, "Note"), (2, "Note")]

    def test_nessun_titolo_trovato_nessun_capitolo(self):
        assert trova_capitoli(["a", "b"], [Titolo("X", "X")]) == []


# ===========================================================================
# Test — inizi_capitoli e metadata_ffmetadata
# ===========================================================================


class TestInizioEMetadata:
    def test_inizi_capitoli_prende_l_inizio_del_paragrafo(self):
        inizi_paragrafi = [0.024, 1.0, 2.5, 4.0]

        risultato = inizi_capitoli(inizi_paragrafi, [(0, "A"), (2, "B")])

        assert risultato == [(0.0, "A"), (2.5, "B")]

    def test_metadata_start_end_in_millisecondi(self):
        testo = metadata_ffmetadata([(0.0, "A"), (1.25, "B")], fine_s=3.5)

        assert testo == (
            ";FFMETADATA1\n"
            "[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=1250\ntitle=A\n"
            "[CHAPTER]\nTIMEBASE=1/1000\nSTART=1250\nEND=3500\ntitle=B\n"
        )

    def test_metadata_escapa_caratteri_speciali(self):
        testo = metadata_ffmetadata([(0.0, "a=b;c#d\\e\nf")], fine_s=1.0)

        assert "title=a\\=b\\;c\\#d\\\\e\\\nf\n" in testo


# ===========================================================================
# Test — timeline_mp3 e unisci_con_capitoli (MP3 reali)
# ===========================================================================


class TestUnisciConCapitoli:
    @pytest.fixture()
    def segmenti(self, sine_mp3) -> list[bytes]:
        return [sine_mp3(1.0, 440), sine_mp3(1.5, 660), sine_mp3(2.0, 880)]

    def test_timeline_inizi_e_durata(self, segmenti):
        mp3 = b"".join(segmenti)
        offsets = [0, len(segmenti[0]), len(segmenti[0]) + len(segmenti[1])]

        inizi, durata = timeline_mp3(mp3, offsets)

        assert inizi[0] == pytest.approx(0.0, abs=0.05)
        assert inizi[1] == pytest.approx(1.0, abs=0.1)
        assert inizi[2] == pytest.approx(2.5, abs=0.15)
        assert durata == pytest.approx(4.5, abs=0.2)

    def test_tre_capitoli_letti_da_ffprobe(self, segmenti, ffprobe_mp3):
        capitoli = [(0, "Primo"), (1, "Secondo è"), (2, "Terzo")]

        info = ffprobe_mp3(unisci_con_capitoli(segmenti, capitoli))

        assert info["titoli"] == ["Primo", "Secondo è", "Terzo"]
        assert info["inizi"][0] == 0.0
        assert info["inizi"][0] < info["inizi"][1] < info["inizi"][2]
        assert abs(info["fine"] - info["durata"]) <= 0.5

    def test_capitolo_su_piu_paragrafi(self, segmenti, ffprobe_mp3):
        info = ffprobe_mp3(unisci_con_capitoli(segmenti, [(0, "A"), (2, "B")]))

        assert info["inizi"][1] == pytest.approx(2.5, abs=0.15)

    def test_audio_non_ricodificato(self, segmenti, tmp_path):
        semplice = b"".join(segmenti)

        con_capitoli = unisci_con_capitoli(segmenti, [(0, "A"), (1, "B")])

        assert _audio_md5(con_capitoli, tmp_path) == _audio_md5(semplice, tmp_path)

    def test_senza_capitoli_byte_identici(self, segmenti):
        assert unisci_con_capitoli(segmenti, []) == b"".join(segmenti)

    def test_nessun_segmento_restituisce_vuoto(self):
        assert unisci_con_capitoli([], []) == b""


# ===========================================================================
# Test — precisione della timeline e percorsi di errore
# ===========================================================================


def _durata_da_pacchetti(mp3: bytes) -> float:
    """Durata del flusso unito misurata da ffprobe contando i pacchetti (576 campioni a 24 kHz)."""
    out = subprocess.run(
        [
            *("ffprobe", "-v", "error", "-f", "mp3", "-i", "pipe:0", "-count_packets"),
            *("-show_entries", "stream=nb_read_packets", "-of", "csv=p=0"),
        ],
        input=mp3,
        capture_output=True,
        check=True,
    ).stdout
    return int(out.decode().strip().rstrip(",")) * 576 / 24000


def _mp3_su_file(durata_s: float, freq: int, tmp_path: Path) -> bytes:
    """MP3 scritto su file seekable: ffmpeg aggiunge l'header Xing/LAME."""
    path = tmp_path / f"seg-{freq}.mp3"
    subprocess.run(
        [
            *("ffmpeg", "-v", "error", "-y", "-f", "lavfi"),
            *("-i", f"sine=frequency={freq}:duration={durata_s}", "-ar", "24000", "-ac", "1"),
            *("-c:a", "libmp3lame", "-b:a", "48k", str(path)),
        ],
        check=True,
    )
    return path.read_bytes()


def _durata_ffprobe_format(mp3: bytes, tmp_path: Path) -> float:
    """Durata di un singolo MP3 come la riporta ffprobe (format=duration)."""
    path = tmp_path / "singolo.mp3"
    path.write_bytes(mp3)
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return float(out.strip())


class TestPrecisioneEErrori:
    def test_inizio_dopo_molte_giunzioni_entro_mezzo_frame(self, tmp_path):
        """Dopo 11 giunzioni l'inizio coincide con la durata reale del tratto precedente.

        Segmenti con header Xing/LAME (scritti su file): ffprobe format=duration ne
        toglie ritardo e padding dell'encoder, ma nel flusso unito quei frame restano,
        quindi una somma delle durate deriva a ogni giunzione.
        """
        segmenti = [_mp3_su_file(0.3, 300 + 50 * i, tmp_path) for i in range(12)]
        prefisso = b"".join(segmenti[:11])
        atteso = _durata_da_pacchetti(prefisso)
        somma_singoli = sum(_durata_ffprobe_format(s, tmp_path) for s in segmenti[:11])

        inizi, _ = timeline_mp3(b"".join(segmenti), [len(prefisso)])

        assert abs(atteso - somma_singoli) > 0.1  # the naive sum really drifts here
        assert inizi[0] == pytest.approx(atteso, abs=0.012)

    def test_mp3_illeggibile_salva_senza_capitoli(self):
        """ffprobe non trova pacchetti: si salva la concatenazione, senza eccezione."""
        assert unisci_con_capitoli([b"non", b"mp3"], [(0, "A")]) == b"nonmp3"

    def test_ffmpeg_assente_salva_senza_capitoli(self, sine_mp3):
        segmenti = [sine_mp3(0.3), sine_mp3(0.3)]

        with patch("src.chapters.subprocess.run", side_effect=FileNotFoundError("ffmpeg")):
            risultato = unisci_con_capitoli(segmenti, [(0, "A"), (1, "B")])

        assert risultato == b"".join(segmenti)

    def test_capitoli_oltre_i_segmenti_salvati_vengono_ignorati(self, sine_mp3, ffprobe_mp3):
        """Salvataggio parziale: un capitolo che inizia dopo l'ultimo paragrafo salvato non c'è."""
        segmenti = [sine_mp3(0.5), sine_mp3(0.5)]

        info = ffprobe_mp3(unisci_con_capitoli(segmenti, [(0, "A"), (1, "B"), (2, "C")]))

        assert info["titoli"] == ["A", "B"]

    def test_capitoli_wav_falliti_lasciano_il_file_senza_capitoli(self, tmp_path, sine_mp3):
        mp3 = tmp_path / "doc.mp3"
        mp3.write_bytes(sine_mp3(0.5))
        originale = mp3.read_bytes()

        with patch("src.chapters.timeline_mp3", side_effect=subprocess.CalledProcessError(1, "x")):
            aggiungi_capitoli_wav(mp3, [_wav(0.5)], [(0, "A")])

        assert mp3.read_bytes() == originale
        assert list(tmp_path.iterdir()) == [mp3]

    def test_capitoli_wav_inizi_dai_campioni(self, tmp_path, sine_mp3, ffprobe_mp3):
        mp3 = tmp_path / "doc.mp3"
        mp3.write_bytes(sine_mp3(2.0))

        aggiungi_capitoli_wav(mp3, [_wav(0.75), _wav(1.25)], [(0, "A"), (1, "B"), (2, "C")])

        info = ffprobe_mp3(mp3)
        assert info["titoli"] == ["A", "B"]
        assert info["inizi"] == [0.0, 0.75]


def _wav(durata_s: float, sample_rate: int = 16000) -> bytes:
    """WAV mono 16 bit di silenzio: per i capitoli conta solo il numero di campioni."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(sample_rate * durata_s))
    return buf.getvalue()


class TestErroriNonMascherati:
    def test_ffprobe_senza_pacchetti_solleva_probe_error(self):
        vuoto = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

        with patch("src.chapters.subprocess.run", return_value=vuoto), pytest.raises(ProbeError):
            timeline_mp3(b"x", [0])

    def test_riga_ffprobe_illeggibile_solleva_probe_error(self):
        rotto = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"N/A,N/A,N/A\n")

        with patch("src.chapters.subprocess.run", return_value=rotto), pytest.raises(ProbeError):
            timeline_mp3(b"x", [0])

    def test_bug_di_indicizzazione_non_diventa_mp3_senza_capitoli(self, sine_mp3):
        """Un errore di programmazione deve emergere, non sparire come "nessun capitolo"."""
        segmenti = [sine_mp3(0.3), sine_mp3(0.3)]

        with (
            patch("src.chapters.inizi_capitoli", side_effect=IndexError("bug")),
            pytest.raises(IndexError),
        ):
            unisci_con_capitoli(segmenti, [(0, "A"), (1, "B")])

    def test_wav_malformato_lascia_il_file_senza_capitoli(self, tmp_path, sine_mp3):
        mp3 = tmp_path / "doc.mp3"
        mp3.write_bytes(sine_mp3(0.3))
        originale = mp3.read_bytes()

        aggiungi_capitoli_wav(mp3, [b"non un wav"], [(0, "A")])

        assert mp3.read_bytes() == originale

    def test_wav_con_framerate_zero_lascia_il_file_senza_capitoli(self, tmp_path, sine_mp3):
        import struct

        mp3 = tmp_path / "doc.mp3"
        mp3.write_bytes(sine_mp3(0.3))
        originale = mp3.read_bytes()
        fmt = struct.pack("<HHIIHH", 1, 1, 0, 0, 2, 16)  # PCM mono, framerate 0
        wav = (
            b"RIFF"
            + struct.pack("<I", 36 + 4)
            + b"WAVE"
            + b"fmt "
            + struct.pack("<I", len(fmt))
            + fmt
            + b"data"
            + struct.pack("<I", 4)
            + b"\x00\x00\x00\x00"
        )

        aggiungi_capitoli_wav(mp3, [wav], [(0, "A")])

        assert mp3.read_bytes() == originale

    def test_output_ffprobe_non_utf8_solleva_probe_error(self):
        binario = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"\xff\xfe")

        with patch("src.chapters.subprocess.run", return_value=binario), pytest.raises(ProbeError):
            timeline_mp3(b"x", [0])
