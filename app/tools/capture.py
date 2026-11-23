"""Capture fixtures from a live source in the managed headed browser.

Usage:
  python -m app.tools.capture <google|yandex|twogis> '<query>' [--city Саратов] [--auto|--manual]

Default --auto: wait for the results list (up to 90 s), save container HTML,
screenshot and captured JSON responses to debug/capture/<source>/<timestamp>/,
then click the first result and save the detail panel the same way.
On consent/captcha/block pages poll every 5 s for up to 10 minutes (a human may
solve it in the visible window), then exit with code 2.

Exit codes: 0 ok, 2 blocked, 3 no results, 130 interrupted.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from app.browser.manager import BrowserManager
from app.logging_setup import setup_logging
from app.paths import DEBUG_DIR, ensure_dirs

RESULTS_WAIT_S = 90
BLOCK_WAIT_S = 600
BLOCK_POLL_S = 5

CITY_SLUGS = {"саратов": "saratov", "энгельс": "engels"}

LIST_SELECTORS = {
    "google": ["[role=feed]", "div[role=main] div[role=region]"],
    "yandex": [".search-list-view__list", ".search-list-view", ".scroll__container"],
    "twogis": ["a[href*='/firm/']"],
}
FIRST_ITEM_SELECTORS = {
    "google": ["[role=feed] a[href*='/maps/place/']", "a[href*='/maps/place/']"],
    "yandex": [".search-list-view__list a[href*='/maps/org/']", "a[href*='/maps/org/']"],
    "twogis": ["a[href*='/firm/']"],
}
DETAIL_SELECTORS = {
    "google": ["div[role=main]", "[role=main]"],
    "yandex": [".business-card-view", ".card-title-view", ".toponym-card-header-view", "[class*='card-view']"],
    "twogis": ["[class*='profile']", "div[data-rubric-id]", "main"],
}


def search_url(source: str, query: str, city: str, domains: dict[str, str] | None = None) -> str:
    domains = domains or {"google": "google.com", "yandex": "yandex.ru", "twogis": "2gis.ru"}
    if source == "google":
        return f"https://www.{domains['google']}/maps/search/{quote_plus(query + ' ' + city)}/?hl=ru"
    if source == "yandex":
        return f"https://{domains['yandex']}/maps/?text={quote_plus(query + ' ' + city)}"
    if source == "twogis":
        slug = CITY_SLUGS.get(city.casefold(), city.casefold())
        return f"https://{domains['twogis']}/{slug}/search/{quote_plus(query)}"
    raise ValueError(f"unknown source {source}")


def _first_visible(page, selectors: list[str]):  # noqa: ANN001, ANN202
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                return loc, sel
        except Exception:  # noqa: BLE001
            continue
    return None, None


def _container_html(page, source: str) -> str:
    """Outer HTML of the results container (scrollable ancestor for 2GIS)."""
    if source == "twogis":
        html = page.evaluate(
            """() => {
                const a = document.querySelector("a[href*='/firm/']");
                if (!a) return document.body ? document.body.outerHTML : '';
                let el = a.parentElement;
                while (el && el !== document.body) {
                    const st = getComputedStyle(el);
                    if ((st.overflowY === 'auto' || st.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 50) {
                        return el.outerHTML;
                    }
                    el = el.parentElement;
                }
                return a.closest('div') ? a.parentElement.outerHTML : document.body.outerHTML;
            }"""
        )
        return html or ""
    loc, _ = _first_visible(page, LIST_SELECTORS[source])
    if loc is not None:
        try:
            return loc.evaluate("el => el.outerHTML")
        except Exception:  # noqa: BLE001
            pass
    return page.content()


def try_accept_consent(page) -> bool:  # noqa: ANN001
    """Click a consent accept button when present (Google consent screen)."""
    for sel in (
        "button[aria-label*='Принять']",
        "button[aria-label*='Accept all']",
        "form[action*='consent'] button",
        "button:has-text('Принять все')",
        "button:has-text('Accept all')",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=3000)
                page.wait_for_timeout(1500)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def wait_for_results(page, mgr: BrowserManager, source: str, stop_wait_s: int = RESULTS_WAIT_S) -> str:
    """Wait for list items; handle blocks by polling for a human. Returns 'ok'|'blocked'|'empty'."""
    deadline = time.monotonic() + stop_wait_s
    while time.monotonic() < deadline:
        reason = mgr.check_block(page, source)
        if reason:
            print(f"[capture] block detected: {reason}; waiting up to 10 min for a human…")
            still = mgr.wait_while_blocked(page, source, timeout_s=BLOCK_WAIT_S, poll_s=BLOCK_POLL_S)
            if still:
                return "blocked"
            deadline = time.monotonic() + stop_wait_s
            continue
        if source == "google":
            try_accept_consent(page)
        loc, _ = _first_visible(page, FIRST_ITEM_SELECTORS[source])
        if loc is not None:
            return "ok"
        page.wait_for_timeout(1000)
    return "empty"


def save_state(page, mgr: BrowserManager, out_dir: Path, label: str, source: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    html = _container_html(page, source) if label == "results" else page.content()
    (out_dir / f"{label}.html").write_text(html, encoding="utf-8")
    try:
        page.screenshot(path=str(out_dir / f"{label}.png"), full_page=False)
    except Exception:  # noqa: BLE001
        pass
    mgr.capture.save(out_dir / "responses")
    (out_dir / "meta.json").write_text(
        json.dumps({"url": page.url, "title": page.title(), "label": label}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def run_capture(
    source: str,
    query: str,
    city: str,
    auto: bool = True,
    out_root: Path | None = None,
    blank: bool = False,
    headless: bool = False,
) -> int:
    setup_logging()
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = (out_root or DEBUG_DIR / "capture") / source / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    mgr = BrowserManager(headless=headless)
    try:
        mgr.start()
        page = mgr.new_page()
        if blank:
            mgr.goto(page, "about:blank")
            save_state(page, mgr, out_dir, "results", source)
            print(f"[capture] blank page saved to {out_dir}")
            return 0

        url = search_url(source, query, city)
        print(f"[capture] {source}: {url}")
        mgr.goto(page, url)
        mgr.human_pause(1.5, 3.0)

        if not auto:
            input("[capture] solve any captcha/consent in the window, then press Enter…")

        state = wait_for_results(page, mgr, source)
        if state == "blocked":
            print("[capture] still blocked after 10 minutes; needs live verification")
            save_state(page, mgr, out_dir, "blocked", source)
            return 2
        if state == "empty":
            print("[capture] no results appeared within the wait window")
            save_state(page, mgr, out_dir, "empty", source)
            return 3

        mgr.human_pause()
        save_state(page, mgr, out_dir, "results", source)
        print(f"[capture] results saved to {out_dir}")

        if not auto:
            input("[capture] press Enter to open the first result…")

        loc, sel = _first_visible(page, FIRST_ITEM_SELECTORS[source])
        if loc is None:
            print("[capture] first result link vanished; skipping detail")
            return 0
        mgr.capture.clear()
        try:
            loc.click(timeout=8000)
        except Exception:  # noqa: BLE001
            print(f"[capture] click failed on {sel}")
            return 0
        detail_deadline = time.monotonic() + 30
        while time.monotonic() < detail_deadline:
            dloc, _ = _first_visible(page, DETAIL_SELECTORS[source])
            if dloc is not None and page.url != url:
                break
            page.wait_for_timeout(700)
        mgr.human_pause(1.5, 3.0)
        save_state(page, mgr, out_dir, "detail", source)
        print(f"[capture] detail saved to {out_dir}")
        return 0
    except KeyboardInterrupt:
        print("[capture] interrupted")
        return 130
    finally:
        mgr.close()


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Capture source fixtures into debug/capture/")
    ap.add_argument("source", choices=["google", "yandex", "twogis"])
    ap.add_argument("query")
    ap.add_argument("--city", default="Саратов")
    ap.add_argument("--auto", action="store_true", default=True, help="non-interactive (default)")
    ap.add_argument("--manual", action="store_true", help="keep Enter prompts")
    ap.add_argument("--blank", action="store_true", help="open about:blank only (self-test)")
    ap.add_argument("--headless", action="store_true", help="run headless (tests only)")
    ap.add_argument("--out", default="", help="output root override")
    args = ap.parse_args(argv)
    return run_capture(
        args.source,
        args.query,
        args.city,
        auto=not args.manual,
        out_root=Path(args.out) if args.out else None,
        blank=args.blank,
        headless=args.headless,
    )


if __name__ == "__main__":
    raise SystemExit(main())
