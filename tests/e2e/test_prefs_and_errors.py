"""Interface language (flow 7), error handling (flow 8), theme and text size (flow 9)."""

import re

from playwright.sync_api import expect

from tests.e2e.reader_page import make_paragraphs


def test_language_switch_translates_interface_and_survives_reload(reader):
    reader.goto()
    reader.load_pasted(make_paragraphs(4))

    reader.page.get_by_role("button", name="EN", exact=True).click()

    expect(reader.counter).to_have_text("Paragraph 1 of 4")
    expect(reader.play).to_have_attribute("aria-label", "Listen")
    expect(reader.meta).to_have_text("4 paragraphs · under a minute of listening")
    expect(reader.page.get_by_role("button", name="EN", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    reader.page.reload()
    expect(reader.page.locator("html")).to_have_attribute("lang", "en")
    expect(reader.page.get_by_role("button", name="Voice and style")).to_be_visible()
    expect(reader.page.get_by_role("button", name="Light theme")).to_be_visible()


def test_language_switch_keeps_player_position_voice_style_and_paused_audio(reader):
    # F12 9657feb: the switch must not reset voice/style nor interrupt the player
    reader.goto()
    reader.choose_voice("isabella")
    reader.choose_style("Audiolibro")
    reader.load_pasted(make_paragraphs(6))
    reader.next.click()
    reader.next.click()
    reader.play.click()
    reader.pause()
    expect(reader.counter).to_have_text("Paragrafo 3 di 6")

    reader.page.get_by_role("button", name="EN", exact=True).click()

    expect(reader.counter).to_have_text("Paragraph 3 of 6")
    expect(reader.voice_summary).to_have_text("Isabella · Audiobook")
    expect(reader.page.get_by_label("Voice", exact=True)).to_have_value("isabella")
    expect(reader.paragraphs.nth(2)).to_have_attribute("aria-current", "true")
    requests_before = len(reader.audio_requests)
    reader.play.click()
    reader.wait_playing(label="Pause")
    assert len(reader.audio_requests) == requests_before


def test_unsupported_extension_shows_message_and_keeps_current_document(reader):
    paragraphs = make_paragraphs(3)
    reader.goto()
    reader.load_pasted(paragraphs)

    reader.upload("foto.xyz", b"not a document", mime="application/octet-stream")

    expect(reader.error).to_contain_text("Formato non supportato. Formati validi:")
    expect(reader.error).to_contain_text(".md")
    expect(reader.paragraphs).to_have_text(paragraphs)
    reader.next.click()
    expect(reader.counter).to_have_text("Paragrafo 2 di 3")
    reader.play.click()
    reader.wait_playing()


def test_empty_file_shows_readable_message_and_keeps_current_document(reader):
    paragraphs = make_paragraphs(3)
    reader.goto()
    reader.load_pasted(paragraphs)

    reader.upload("vuoto.txt", b"  \n\n  \n")

    expect(reader.error).to_contain_text("In questo file non ho trovato testo da leggere")
    expect(reader.paragraphs).to_have_text(paragraphs)
    expect(reader.title).to_have_text("Testo incollato")
    reader.page.get_by_role("button", name="Chiudi messaggio di errore").click()
    expect(reader.error).to_be_hidden()


def test_online_voice_failure_offers_offline_voice_and_retry_uses_it(reader):
    def fail_online(route):
        if "voice=paola" in route.request.url:
            route.continue_()
        else:
            route.fulfill(
                status=503,
                content_type="application/json",
                body='{"error": "La voce Giuseppe non risponde.", "fallback_voice": "paola"}',
            )

    reader.page.route("**/api/audio/**", fail_online)
    reader.goto()
    reader.load_pasted(make_paragraphs(3))

    reader.play.click()

    expect(reader.error).to_contain_text("La voce Giuseppe non risponde.")
    offer = reader.page.get_by_role("button", name="Ascolta con Paola (senza internet)")
    expect(offer).to_be_visible()
    with reader.page.expect_request(lambda r: "/api/audio/0" in r.url and "voice=paola" in r.url):
        offer.click()
    reader.wait_playing()
    expect(reader.error).to_be_hidden()
    expect(reader.voice_summary).to_have_text("Paola · Neutro")


def test_dark_theme_is_default_and_light_theme_persists_after_reload(reader):
    reader.goto()
    html = reader.page.locator("html")
    toggle = reader.page.get_by_role("button", name="Tema chiaro")
    expect(html).not_to_have_attribute("data-theme", "light")
    expect(toggle).to_have_attribute("aria-pressed", "false")

    toggle.click()

    expect(html).to_have_attribute("data-theme", "light")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    reader.page.reload()
    expect(html).to_have_attribute("data-theme", "light")
    expect(reader.page.get_by_role("button", name="Tema chiaro")).to_have_attribute(
        "aria-pressed", "true"
    )
    reader.page.get_by_role("button", name="Tema chiaro").click()
    expect(html).not_to_have_attribute("data-theme", "light")


def _para_font_px(reader) -> float:
    return reader.page.evaluate(
        "el => parseFloat(getComputedStyle(el).fontSize)", reader.paragraphs.first.element_handle()
    )


def test_text_size_scales_reading_text_limits_at_edges_and_persists(reader):
    reader.goto()
    reader.load_pasted(make_paragraphs(2))
    smaller = reader.page.get_by_role("button", name="Testo più piccolo")
    larger = reader.page.get_by_role("button", name="Testo più grande")
    base = _para_font_px(reader)

    larger.click()
    larger.click()
    expect(larger).to_be_enabled()

    assert abs(_para_font_px(reader) - base * 1.3) < 0.5
    reader.page.reload()
    reader.load_pasted(make_paragraphs(2))
    assert abs(_para_font_px(reader) - base * 1.3) < 0.5
    larger.click()
    expect(larger).to_be_disabled()
    assert abs(_para_font_px(reader) - base * 1.5) < 0.5
    for _ in range(4):
        smaller.click()
    expect(smaller).to_be_disabled()
    assert abs(_para_font_px(reader) - base * 0.85) < 0.5
    assert re.fullmatch(
        r"\d+(\.\d+)?",
        reader.page.evaluate("document.documentElement.style.getPropertyValue('--reading-scale')"),
    )
