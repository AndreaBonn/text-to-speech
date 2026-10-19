"""Smoke test of the e2e harness: the page loads and the app answers."""

from playwright.sync_api import expect


def test_page_loads_with_title(page, live_app):
    page.goto(live_app.url)

    expect(page).to_have_title("Lettore ad alta voce")
