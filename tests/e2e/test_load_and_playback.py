"""Loading documents, play, pause/resume and navigation (flows 1-4)."""

import re

from playwright.sync_api import expect

from tests.e2e.reader_page import audio_query, join_text, make_paragraphs


def test_pasted_text_shows_paragraphs_in_order_with_title_and_estimate(reader):
    # 4 paragraphs x 900 chars = 3600 chars at 15 chars/s = 240 s = 4 minutes
    paragraphs = make_paragraphs(4, length=900)
    reader.goto()

    reader.paste(join_text(paragraphs))

    expect(reader.paragraphs).to_have_text(paragraphs)
    expect(reader.title).to_have_text("Testo incollato")
    expect(reader.meta).to_have_text("4 paragrafi · circa 4 minuti di ascolto")
    expect(reader.counter).to_have_text("Paragrafo 1 di 4")


def test_uploaded_md_file_shows_its_name_title_and_paragraphs(reader):
    paragraphs = make_paragraphs(3)
    reader.goto()

    reader.upload("guida rapida.md", join_text(paragraphs).encode(), mime="text/markdown")

    expect(reader.paragraphs).to_have_text(paragraphs)
    expect(reader.page.locator("#file-name")).to_have_text("guida rapida.md")
    expect(reader.title).to_have_text("guida rapida")
    expect(reader.meta).to_have_text("3 paragrafi · meno di un minuto di ascolto")


def test_play_uses_voice_and_style_chosen_in_the_panel(reader, live_app):
    paragraphs = make_paragraphs(3)
    reader.goto()
    reader.choose_voice("isabella")
    reader.choose_style("Lento")
    # The first paragraph is prefetched as soon as the document is loaded
    with reader.page.expect_request(lambda r: "/api/audio/0" in r.url) as req:
        reader.load_pasted(paragraphs)

    reader.play.click()

    reader.wait_playing()
    assert audio_query(req.value) == {"voice": "isabella", "style": "lento"}
    expect(reader.paragraphs.nth(0)).to_have_attribute("aria-current", "true")
    assert (paragraphs[0], "isabella", "lento") in live_app.synth_calls


def test_audio_end_moves_highlight_to_next_paragraph(reader):
    reader.goto()
    reader.load_pasted(make_paragraphs(8))

    with reader.page.expect_request(lambda r: "/api/audio/1" in r.url):
        reader.play.click()

    expect(reader.paragraphs.nth(0)).to_have_class(re.compile(r"\bis-done\b"))
    expect(reader.paragraphs.nth(1)).to_have_class(re.compile(r"\bis-current\b"))
    expect(reader.counter).to_have_text(re.compile(r"Paragrafo [2-8] di 8"))


def test_pause_then_play_resumes_same_audio_without_new_request(reader):
    reader.goto()
    reader.load_pasted(make_paragraphs(8))
    reader.play.click()
    reader.pause()
    src_before = reader.page.evaluate("player._audio.src")
    assert reader.audio_count(0) == 1

    reader.play.click()

    reader.wait_playing()
    assert reader.page.evaluate("player._audio.src") == src_before
    assert reader.audio_count(0) == 1


def test_changing_voice_while_paused_resynthesizes_instead_of_resuming(reader):
    # F1 20036d5: the paused audio of the old voice must not be resumed
    reader.goto()
    reader.load_pasted(make_paragraphs(8))
    reader.play.click()
    reader.pause()
    reader.choose_voice("diego")

    with reader.page.expect_request(lambda r: "/api/audio/0" in r.url and "voice=diego" in r.url):
        reader.play.click()

    reader.wait_playing()


def test_moving_to_another_paragraph_while_paused_plays_that_paragraph(reader):
    # F1 20036d5: Avanti while paused moved the highlight but resumed the old audio
    reader.goto()
    reader.load_pasted(make_paragraphs(8))
    reader.play.click()
    reader.pause()
    reader.next.click()
    reader.next.click()
    expect(reader.counter).to_have_text("Paragrafo 3 di 8")

    with reader.page.expect_request(lambda r: "/api/audio/2" in r.url):
        reader.play.click()

    reader.wait_playing()


def test_click_on_paragraph_while_paused_reads_from_there(reader):
    reader.goto()
    reader.load_pasted(make_paragraphs(8))
    reader.play.click()
    reader.pause()

    with reader.page.expect_request(lambda r: "/api/audio/5" in r.url):
        reader.paragraphs.nth(5).click()

    expect(reader.paragraphs.nth(5)).to_have_attribute("aria-current", "true")


def test_prev_next_and_start_buttons_move_and_disable_at_bounds(reader):
    reader.goto()
    reader.load_pasted(make_paragraphs(4))
    start = reader.page.get_by_role("button", name="Torna all'inizio")
    expect(reader.prev).to_be_disabled()
    expect(start).to_be_disabled()

    reader.next.click()
    reader.next.click()
    reader.next.click()

    expect(reader.counter).to_have_text("Paragrafo 4 di 4")
    expect(reader.next).to_be_disabled()
    reader.prev.click()
    expect(reader.counter).to_have_text("Paragrafo 3 di 4")
    start.click()
    expect(reader.counter).to_have_text("Paragrafo 1 di 4")
    expect(reader.paragraphs.nth(0)).to_have_attribute("aria-current", "true")


def test_keyboard_shortcuts_navigate_and_toggle_playback(reader):
    reader.goto()
    reader.load_pasted(make_paragraphs(8))
    reader.blur_focus()

    reader.page.keyboard.press("ArrowRight")
    reader.page.keyboard.press("ArrowRight")
    expect(reader.counter).to_have_text("Paragrafo 3 di 8")
    reader.page.keyboard.press("ArrowLeft")
    expect(reader.counter).to_have_text("Paragrafo 2 di 8")

    with reader.page.expect_request(lambda r: "/api/audio/1" in r.url):
        reader.page.keyboard.press("Space")
    reader.wait_playing()
    reader.page.keyboard.press("Space")
    expect(reader.play).to_have_attribute("aria-label", "Ascolta")


def test_play_after_changing_style_requests_audio_with_new_style(reader):
    # The prefetch made at load time is dropped on a style change: Play fetches directly
    reader.goto()
    reader.load_pasted(make_paragraphs(4))
    reader.choose_style("Audiolibro")

    with reader.page.expect_request(lambda r: "/api/audio/0" in r.url) as req:
        reader.play.click()

    assert audio_query(req.value) == {"voice": "giuseppe", "style": "audiolibro"}


def test_jump_to_not_prefetched_paragraph_requests_it_with_chosen_voice_and_style(reader):
    reader.goto()
    reader.choose_voice("elsa")
    reader.choose_style("Notiziario")
    reader.load_pasted(make_paragraphs(6))

    with reader.page.expect_request(lambda r: "/api/audio/4" in r.url) as req:
        reader.paragraphs.nth(4).click()

    assert audio_query(req.value) == {"voice": "elsa", "style": "notiziario"}
