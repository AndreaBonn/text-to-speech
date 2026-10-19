"""Resume offer (flow 5) and MP3 download (flow 6)."""

import threading
from unittest.mock import patch

from playwright.sync_api import expect

from tests.e2e.reader_page import make_paragraphs

RESUME_TEXT = "L'ultima volta eri arrivato al paragrafo 4 di 5."


def _read_up_to_paragraph_4_then_reload(reader, paragraphs):
    reader.goto()
    reader.load_pasted(paragraphs)
    for _ in range(3):
        reader.next.click()
    expect(reader.counter).to_have_text("Paragrafo 4 di 5")
    reader.goto()


def test_reloading_same_text_offers_to_resume_and_resume_plays_from_there(reader):
    paragraphs = make_paragraphs(5)
    _read_up_to_paragraph_4_then_reload(reader, paragraphs)

    reader.load_pasted(paragraphs)

    note = reader.page.locator("#resume-note")
    expect(note).to_contain_text(RESUME_TEXT)
    with reader.page.expect_request(lambda r: "/api/audio/3" in r.url):
        reader.page.get_by_role("button", name="Riprendi da qui").click()
    expect(note).to_be_hidden()
    expect(reader.paragraphs.nth(3)).to_have_attribute("aria-current", "true")


def test_resume_note_start_over_keeps_first_paragraph(reader):
    paragraphs = make_paragraphs(5)
    _read_up_to_paragraph_4_then_reload(reader, paragraphs)
    reader.load_pasted(paragraphs)
    expect(reader.page.locator("#resume-note")).to_contain_text(RESUME_TEXT)

    reader.page.get_by_role("button", name="Dall'inizio").first.click()

    expect(reader.page.locator("#resume-note")).to_be_hidden()
    expect(reader.counter).to_have_text("Paragrafo 1 di 5")


def test_different_text_with_same_paragraph_count_gets_no_resume_offer(reader):
    # F6 9657feb: two pasted texts with the same paragraph count shared a position
    paragraphs = make_paragraphs(5)
    _read_up_to_paragraph_4_then_reload(reader, paragraphs)

    other = [p.replace("numero", "altro") for p in paragraphs]
    reader.load_pasted(other)

    expect(reader.page.locator("#resume-note")).to_be_hidden()
    expect(reader.counter).to_have_text("Paragrafo 1 di 5")


def test_save_mp3_downloads_file_named_after_document_with_progress(reader, live_app):
    from src.app import engine

    paragraphs = make_paragraphs(4)
    release = threading.Event()
    real_synth = engine._synthesize_text

    def gated_synth(text, voice, style="neutro", timeout=None):
        # Hold the third paragraph so the progress poll can observe "2 di 4"
        if text == paragraphs[2]:
            assert release.wait(20), "test never released the synthesis"
        return real_synth(text, voice, style)

    reader.goto()
    reader.upload("racconto lungo.txt", "\n\n".join(paragraphs).encode())
    expect(reader.paragraphs).to_have_count(4)
    engine._cache.clear()  # cached paragraphs would skip the gated synthesis
    status = reader.page.locator("#save-status")

    save_button = reader.page.get_by_role("button", name="Scarica audio completo")
    with (
        patch.object(engine, "_synthesize_text", side_effect=gated_synth),
        reader.page.expect_download() as download,
    ):
        save_button.click()
        expect(status).to_contain_text("Preparo l'MP3: 2 di 4 paragrafi pronti")
        expect(save_button).to_be_disabled()
        release.set()

    assert download.value.suggested_filename == "racconto lungo.mp3"
    expect(status).to_have_text("MP3 scaricato: racconto lungo.mp3")
    expect(status).to_be_hidden(timeout=10000)
    expect(reader.page.get_by_role("button", name="Scarica audio completo")).to_be_enabled()


def test_position_at_second_paragraph_is_remembered_and_offered(reader):
    paragraphs = make_paragraphs(5)
    reader.goto()
    reader.load_pasted(paragraphs)
    reader.next.click()
    expect(reader.counter).to_have_text("Paragrafo 2 di 5")
    reader.goto()

    reader.load_pasted(paragraphs)

    expect(reader.page.locator("#resume-note")).to_contain_text(
        "L'ultima volta eri arrivato al paragrafo 2 di 5."
    )
    with reader.page.expect_request(lambda r: "/api/audio/1" in r.url):
        reader.page.get_by_role("button", name="Riprendi da qui").click()


def test_listening_to_the_end_clears_the_resume_position(reader):
    # e4f35ce: the position is "cleared when a document is listened to the end"
    paragraphs = make_paragraphs(3)
    reader.goto()
    reader.load_pasted(paragraphs)

    reader.play.click()
    reader.wait_playing()
    expect(reader.counter).to_have_text("Paragrafo 3 di 3", timeout=15000)
    expect(reader.play).to_have_attribute("aria-label", "Ascolta", timeout=15000)

    reader.goto()
    reader.load_pasted(paragraphs)

    expect(reader.counter).to_have_text("Paragrafo 1 di 3")
    expect(reader.page.locator("#resume-note")).to_be_hidden()
