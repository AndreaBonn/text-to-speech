"""
tests/test_config.py
Tabelle di configurazione dichiarate nel README: stili di lettura (velocità, tono)
e stile suggerito per estensione. Gli oracoli sono scritti a mano dal README.
"""

import pytest

from src.config import DEFAULT_STYLE, FILE_STYLE_DEFAULTS, READING_STYLES


class TestReadingStyles:
    @pytest.mark.parametrize(
        ("style", "rate", "pitch"),
        [
            ("neutro", "+0%", "+0Hz"),
            ("notiziario", "+13%", "+5Hz"),
            ("audiolibro", "-8%", "-3Hz"),
            ("lento", "-20%", "+0Hz"),
        ],
    )
    def test_stile_ha_velocita_e_tono_del_readme(self, style, rate, pitch):
        assert READING_STYLES[style] == {"rate": rate, "pitch": pitch}

    def test_gli_stili_sono_esattamente_i_quattro_del_readme(self):
        assert set(READING_STYLES) == {"neutro", "notiziario", "audiolibro", "lento"}

    def test_stile_predefinito_e_neutro(self):
        assert DEFAULT_STYLE == "neutro"


class TestFileStyleDefaults:
    @pytest.mark.parametrize(
        ("extension", "style"),
        [
            (".epub", "audiolibro"),
            (".md", "notiziario"),
            (".html", "notiziario"),
            (".htm", "notiziario"),
            (".txt", "neutro"),
            (".docx", "neutro"),
            (".pdf", "neutro"),
        ],
    )
    def test_stile_suggerito_per_estensione_come_da_readme(self, extension, style):
        assert FILE_STYLE_DEFAULTS[extension] == style

    def test_ogni_estensione_suggerisce_uno_stile_esistente(self):
        assert set(FILE_STYLE_DEFAULTS.values()) <= set(READING_STYLES)
