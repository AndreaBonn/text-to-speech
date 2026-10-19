"""Page object of the reader UI: locators and the few actions every test shares."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Request, expect

DEFAULT_SUMMARY = "Giuseppe · Neutro"


def make_paragraphs(count: int, length: int | None = None) -> list[str]:
    """`count` distinct paragraphs; with `length` each has exactly that many characters."""
    out = []
    for n in range(1, count + 1):
        base = f"Paragrafo numero {n} del testo di prova."
        out.append(base if length is None else base + " " + "a" * (length - len(base) - 1))
    return out


def join_text(paragraphs: list[str]) -> str:
    return "\n\n".join(paragraphs)


def audio_query(request: Request) -> dict[str, str]:
    """voice/style of an /api/audio request."""
    return {k: v[0] for k, v in parse_qs(urlparse(request.url).query).items()}


class ReaderPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.audio_requests: list[str] = []
        page.on("request", self._record)

        self.play = page.locator("#btn-play")
        self.next = page.locator("#btn-next")
        self.prev = page.locator("#btn-prev")
        self.counter = page.locator("#progress-counter")
        self.paragraphs = page.locator("#reader-text").get_by_role("paragraph")
        self.title = page.locator("#doc-title")
        self.meta = page.locator("#doc-meta")
        self.error = page.get_by_role("alert")
        self.voice_summary = page.locator("#voice-summary")

    def _record(self, request: Request) -> None:
        if "/api/audio/" in request.url:
            self.audio_requests.append(request.url)

    def audio_count(self, idx: int) -> int:
        return sum(1 for u in self.audio_requests if urlparse(u).path == f"/api/audio/{idx}")

    def goto(self) -> None:
        self.page.goto(self.base_url)
        # The voice list is loaded asynchronously: wait for it before interacting.
        expect(self.voice_summary).to_have_text(DEFAULT_SUMMARY)

    def paste(self, text: str) -> None:
        self.page.get_by_role("button", name="oppure incolla un testo").click()
        self.page.get_by_label("Testo da ascoltare").fill(text)
        self.page.get_by_role("button", name="Ascolta questo testo").click()

    def upload(self, name: str, content: bytes, mime: str = "text/plain") -> None:
        self.page.get_by_label("Scegli file da leggere").set_input_files(
            files=[{"name": name, "mimeType": mime, "buffer": content}]
        )

    def load_pasted(self, paragraphs: list[str]) -> None:
        self.paste(join_text(paragraphs))
        expect(self.paragraphs).to_have_count(len(paragraphs))

    def open_voice_panel(self) -> None:
        toggle = self.page.get_by_role("button", name="Voce e stile")
        if toggle.get_attribute("aria-expanded") != "true":
            toggle.click()

    def choose_voice(self, voice_id: str) -> None:
        self.open_voice_panel()
        self.page.get_by_label("Voce", exact=True).select_option(voice_id)

    def choose_style(self, label: str) -> None:
        self.open_voice_panel()
        self.page.get_by_role("radio", name=label).check()

    def blur_focus(self) -> None:
        """Keyboard shortcuts are ignored on inputs: park the focus on the body."""
        self.page.evaluate("document.activeElement.blur()")

    def wait_playing(self, label: str = "Pausa") -> None:
        expect(self.play).to_have_attribute("aria-label", label)

    def pause(self) -> None:
        self.wait_playing()
        self.play.click()
        expect(self.play).to_have_attribute("aria-label", "Ascolta")
