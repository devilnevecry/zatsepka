"""Managed headed browser: sync Playwright, persistent profile, response capture.

Rules (SPEC 4): sync API only inside a worker thread or CLI tool, never inside a
running asyncio loop; one context per job reused across sources; one profile
instance at a time (cross-process lock file); no stealth or fingerprint spoofing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import psutil
from playwright.sync_api import BrowserContext, Page, Response, sync_playwright

from app.browser.blocks import detect_block
from app.paths import BROWSER_LOCK_PATH, BROWSER_PROFILE_DIR, ensure_dirs

log = logging.getLogger(__name__)

MAX_CAPTURED = 200
MAX_BODY_BYTES = 2 * 1024 * 1024
RECYCLE_EVERY_PAGES = 200
VIEWPORT = {"width": 1366, "height": 850}

_JSON_URL_HINTS = ("tbm=map", "/maps/api", "/maps/preview", "catalog.api", "/search?", "api.2gis", "dispatcher")


class BrowserBusyError(RuntimeError):
    """Another process or thread already owns the browser profile."""


class NeedsHumanError(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _assert_not_in_asyncio() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise RuntimeError("Sync Playwright must run in a worker thread, not inside the asyncio loop")


@dataclass
class CapturedResponse:
    url: str
    status: int
    content_type: str
    body: bytes
    truncated: bool = False
    ts: float = field(default_factory=time.time)


class ResponseCapture:
    """Bounded deque of JSON-ish responses the page itself fetched."""

    def __init__(self, maxlen: int = MAX_CAPTURED):
        self.items: deque[CapturedResponse] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def _looks_interesting(self, response: Response) -> bool:
        url = response.url
        if url.startswith("data:"):
            return False
        ctype = (response.headers or {}).get("content-type", "")
        if "json" in ctype:
            return True
        return any(hint in url for hint in _JSON_URL_HINTS)

    def attach(self, page: Page) -> None:
        def on_response(response: Response) -> None:
            try:
                if not self._looks_interesting(response):
                    return
                body = response.body()
                truncated = len(body) > MAX_BODY_BYTES
                if truncated:
                    body = body[:MAX_BODY_BYTES]
                item = CapturedResponse(
                    url=response.url,
                    status=response.status,
                    content_type=(response.headers or {}).get("content-type", ""),
                    body=body,
                    truncated=truncated,
                )
                with self._lock:
                    self.items.append(item)
            except Exception:  # noqa: BLE001 - body may be gone after navigation
                pass

        page.on("response", on_response)

    def snapshot(self) -> list[CapturedResponse]:
        with self._lock:
            return list(self.items)

    def clear(self) -> None:
        with self._lock:
            self.items.clear()

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        manifest = []
        for i, item in enumerate(self.snapshot()):
            name = f"resp_{i:04d}.json"
            (directory / name).write_bytes(item.body)
            manifest.append(
                {
                    "file": name,
                    "url": item.url,
                    "status": item.status,
                    "content_type": item.content_type,
                    "size": len(item.body),
                    "truncated": item.truncated,
                }
            )
        manifest_path = directory / "responses.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        return manifest_path


class ProfileLock:
    """Cross-process single-instance lock for the browser profile."""

    def __init__(self, path: Path = BROWSER_LOCK_PATH):
        self.path = path
        self._owned = False

    def acquire(self) -> None:
        ensure_dirs()
        if self.path.exists():
            try:
                pid = int(self.path.read_text(encoding="utf-8").strip() or "0")
            except ValueError:
                pid = 0
            if pid and pid != os.getpid() and psutil.pid_exists(pid):
                raise BrowserBusyError(f"Browser profile is in use by pid {pid}")
        self.path.write_text(str(os.getpid()), encoding="utf-8")
        self._owned = True

    def release(self) -> None:
        if self._owned:
            try:
                if self.path.exists() and self.path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                    self.path.unlink()
            except OSError:
                pass
            self._owned = False


class BrowserManager:
    """One persistent context, reused across sources; recycled every N pages."""

    _process_lock = threading.Lock()

    def __init__(self, headless: bool = False, chrome_path: str = "", profile_dir: Path | None = None):
        _assert_not_in_asyncio()
        self.headless = headless
        self.chrome_path = chrome_path
        self.profile_dir = profile_dir or BROWSER_PROFILE_DIR
        self.capture = ResponseCapture()
        self._pw = None
        self._context: BrowserContext | None = None
        self._profile_lock = ProfileLock()
        self._pages_opened = 0
        self._started = False

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> BrowserManager:
        if self._started:
            return self
        if not BrowserManager._process_lock.acquire(blocking=False):
            raise BrowserBusyError("Another BrowserManager is active in this process")
        try:
            self._profile_lock.acquire()
            self._pw = sync_playwright().start()
            self._context = self._launch_context()
            self._started = True
            return self
        except Exception:
            self._cleanup()
            raise

    def _launch_context(self) -> BrowserContext:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        common = {
            "user_data_dir": str(self.profile_dir),
            "headless": self.headless,
            "locale": "ru-RU",
            "viewport": VIEWPORT,
            "args": ["--start-maximized"],
            "no_viewport": False,
        }
        if self.chrome_path:
            return self._pw.chromium.launch_persistent_context(executable_path=self.chrome_path, **common)
        try:
            return self._pw.chromium.launch_persistent_context(channel="chrome", **common)
        except Exception as exc:  # noqa: BLE001 - fall back to bundled chromium
            log.warning("Chrome channel unavailable (%s); falling back to bundled chromium", exc)
            return self._pw.chromium.launch_persistent_context(**common)

    def close(self) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._context = None
        self._pw = None
        self._profile_lock.release()
        if self._started:
            try:
                BrowserManager._process_lock.release()
            except RuntimeError:
                pass
        self._started = False

    def __enter__(self) -> BrowserManager:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    # -- pages -------------------------------------------------------------
    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("BrowserManager is not started")
        return self._context

    def new_page(self) -> Page:
        if self._pages_opened >= RECYCLE_EVERY_PAGES:
            self.recycle()
        page = self.context.new_page()
        self.capture.attach(page)
        self._pages_opened += 1
        return page

    def recycle(self) -> None:
        """Close and relaunch the context (browser context recycling hook)."""
        log.info("Recycling browser context after %s pages", self._pages_opened)
        try:
            if self._context is not None:
                self._context.close()
        except Exception:  # noqa: BLE001
            pass
        self._context = self._launch_context()
        self._pages_opened = 0
        self.capture.clear()

    # -- helpers -----------------------------------------------------------
    def human_pause(self, low: float = 0.8, high: float = 2.5) -> None:
        time.sleep(random.uniform(low, high))

    def goto(self, page: Page, url: str, timeout_ms: int = 45000) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

    def check_block(self, page: Page, source: str) -> str | None:
        try:
            title = page.title()
        except Exception:  # noqa: BLE001
            title = ""
        try:
            text = page.inner_text("body", timeout=3000)
        except Exception:  # noqa: BLE001
            text = ""
        return detect_block(source, page.url, title, text)

    def wait_while_blocked(
        self,
        page: Page,
        source: str,
        stop_event: threading.Event | None = None,
        timeout_s: float = 600.0,
        poll_s: float = 5.0,
        on_blocked=None,
        on_cleared=None,
    ) -> str | None:
        """Poll every poll_s up to timeout_s while a human may solve the block.

        Returns the last reason if still blocked after the timeout, else None.
        """
        deadline = time.monotonic() + timeout_s
        notified = False
        while time.monotonic() < deadline:
            if stop_event is not None and stop_event.is_set():
                return "stopped"
            reason = self.check_block(page, source)
            if reason is None:
                if notified and on_cleared is not None:
                    on_cleared()
                return None
            if not notified:
                notified = True
                if on_blocked is not None:
                    on_blocked(reason)
            time.sleep(poll_s)
        return self.check_block(page, source) or "timeout"
