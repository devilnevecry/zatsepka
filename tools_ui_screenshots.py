"""Capture screenshots of every page at 1440x900 into debug/ui/."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

from app.main import create_app

OUT = Path("debug/ui")

PAGES = [
    ("search", "/"),
    ("dashboard", "/page/dashboard"),
    ("profile", "/page/profile"),
    ("chats", "/page/chats"),
    ("otbor", "/page/otbor"),
    ("messages", "/page/messages"),
    ("ai", "/page/ai"),
    ("base", "/page/base"),
    ("keys", "/page/keys"),
    ("charts", "/page/charts"),
    ("settings", "/page/settings"),
    ("help", "/page/help"),
    ("diagnostics", "/page/diagnostics"),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=8768, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(60):
        if server.started:
            break
        time.sleep(0.1)
    errors_total = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            for name, path in PAGES:
                page.goto(f"http://127.0.0.1:8768{path}", wait_until="networkidle")
                page.wait_for_timeout(250)
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
                print(f"[ui] {name}: ok")
            browser.close()
            errors_total = len(errors)
            if errors:
                print(f"[ui] console errors: {errors[:5]}")
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    return 1 if errors_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
