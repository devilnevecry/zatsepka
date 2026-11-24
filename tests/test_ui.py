"""UI smoke tests: pages render with no JS console errors / failed requests."""

from __future__ import annotations

import pytest
from playwright.sync_api import sync_playwright


@pytest.mark.e2e
def test_ui_pages_smoke(tmp_db):
    import threading
    import time

    import uvicorn

    from app.main import create_app

    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            failed = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("requestfailed", lambda r: failed.append(r.url))
            for path, expected in (
                ("/", "Парсер"),
                ("/page/settings", "Настройки"),
                ("/page/profile", "Профиль"),
                ("/page/charts", "Графики"),
                ("/page/help", "Помощь"),
            ):
                page.goto(f"http://127.0.0.1:8765{path}", wait_until="networkidle")
                assert expected in page.content()
            page.goto("http://127.0.0.1:8765/", wait_until="networkidle")
            assert page.locator("#city-chips").count() == 1
            assert page.locator("#card-grid").count() == 1
            assert page.locator("#start-btn").count() == 1
            before = page.locator("body").get_attribute("class")
            page.locator("#theme-toggle").click()
            after = page.locator("body").get_attribute("class")
            assert before != after and ("theme-light" in after or "theme-dark" in after)
            page.screenshot(path="debug/ui_search.png", full_page=False)
            browser.close()
            assert errors == [], f"console errors: {errors[:5]}"
            assert failed == [], f"failed requests: {failed[:5]}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@pytest.mark.e2e
def test_ui_job_flow_with_fake_scrapers(tmp_db, monkeypatch):
    import threading
    import time

    import uvicorn

    from app.main import create_app
    from app.scrapers.base import RawPlace
    from app.web import state as web_state

    class FakeScraper:
        def iter_places(self, query, city, max_results, stop_event=None, on_progress=None):
            yield RawPlace(name="Барбершоп Тест", city="Саратов", category="барбершоп", phones=["+78452111111"])

    web_state.runner.scraper_factory = lambda source, city: FakeScraper()
    monkeypatch.setattr(web_state.runner, "scraper_factory", lambda source, city: FakeScraper())

    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=8767, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto("http://127.0.0.1:8767/", wait_until="networkidle")
            page.locator("#start-btn").click()
            page.wait_for_selector(".lead-card", timeout=20000)
            assert "Барбершоп Тест" in page.locator(".lead-card").first.inner_text()
            page.locator("#stop-btn").click()
            browser.close()
            assert errors == [], errors[:3]
    finally:
        monkeypatch.setattr(web_state.runner, "scraper_factory", None)
        server.should_exit = True
        thread.join(timeout=10)
