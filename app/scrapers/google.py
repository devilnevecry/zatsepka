"""Google Maps scraper: pure parsers + thin browser layer (stage 2)."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from typing import Any

from playwright.sync_api import Page

from app.browser.manager import BrowserManager, NeedsHumanError
from app.scrapers.base import BaseScraper, RawPlace, SourceChanged


def _norm_phone(raw: Any) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return "+" + digits


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def parse_google_payload(data: Any) -> list[RawPlace]:  # noqa: ANN001, ANN202
    """Parse captured Google search JSON 'd' array into RawPlace list (pure fn)."""
    out: list[RawPlace] = []
    if not isinstance(data, list) or not data or not isinstance(data[0], list) or len(data[0]) < 2:
        return out
    page_key = data[0][1]
    items = _as_list(page_key)[1:]
    for el in items:
        if not isinstance(el, list) or len(el) < 15 or not isinstance(el[14], dict):
            continue
        place = el[14]
        phones_raw = _as_list(place.get(178))
        phones: list[str] = []
        phone_group = _as_list(phones_raw[0]) if phones_raw else []
        phone = phone_group[3] if len(phone_group) > 3 else None
        if phone:
            phones.append(_norm_phone(phone))
        rating = _as_list(place.get(4))[7] if len(_as_list(place.get(4))) > 7 else None
        reviews = _as_list(place.get(4))[8] if len(_as_list(place.get(4))) > 8 else None
        website = _as_list(place.get(7))[0] if len(_as_list(place.get(7))) > 0 and _as_list(place.get(7))[0] else None
        lat = _as_list(place.get(9))[2] if len(_as_list(place.get(9))) > 2 else None
        lon = _as_list(place.get(9))[3] if len(_as_list(place.get(9))) > 3 else None
        photos = _as_list(place.get(37))[1] if len(_as_list(place.get(37))) > 1 else None
        raw_categories = place.get(13)
        category = ", ".join(str(c) for c in _as_list(raw_categories) if c) if _as_list(raw_categories) else str(raw_categories or "")
        hours: dict[str, str] = {}
        for h in _as_list(place.get(203)):
            if isinstance(h, list) and len(h) > 1 and h[0] and len(h[1]) > 0:
                hours[str(h[0])] = str(h[1][0])
        attributes = _as_list(_as_list(place.get(100))[1])
        out.append(
            RawPlace(
                source="google",
                source_id=str(place.get(10) or ""),
                url=f"https://www.google.com/maps?q={place.get(11) or ''}",
                name=str(place.get(11) or ""),
                category=category,
                address=str(place.get(39) or ""),
                lat=float(lat) if isinstance(lat, (int, float)) else None,
                lon=float(lon) if isinstance(lon, (int, float)) else None,
                phones=phones,
                emails=[],
                website=str(website or ""),
                socials={},
                rating=float(rating) if isinstance(rating, (int, float)) else None,
                reviews_count=int(reviews) if isinstance(reviews, (int, float)) else None,
                description=str(_as_list(place.get(161))[1] or ""),
                hours=hours,
                attributes=[str(a) for a in attributes if a],
                price_range=str(_as_list(place.get(4))[2] or "") if len(_as_list(place.get(4))) > 2 else "",
                plus_code="",
                photos_count=int(photos) if isinstance(photos, (int, float)) else None,
                top_reviews=[],
                extra={"cid": str(place.get(10) or ""), "datafid": str(place.get(10) or "")},
            )
        )
    return out


class GoogleScraper(BaseScraper):
    source = "google"
    list_selector = "[role=feed]"
    item_selector = '[role=feed] a[href*="/maps/place/"]'

    def __init__(self, manager: BrowserManager | None = None):
        super().__init__()
        self.manager = manager or BrowserManager(headless=True)

    def _wait_for_articles(self, page: Page, timeout_ms: int = 60000) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if page.locator(self.item_selector).count() > 0:
                return
            page.wait_for_timeout(500)
        raise SourceChanged("no result articles appeared in the feed")

    def iter_places(self, query: str, city: str, max_results: int, stop_event: threading.Event | None = None, on_progress=None) -> Iterator[RawPlace]:
        if stop_event is None:
            stop_event = threading.Event()
        mgr = self.manager
        page = mgr.new_page()
        try:
            url = f"https://www.google.com/maps/search/{query.replace(' ', '+')} {city}?hl=ru&tbm=map"
            mgr.goto(page, url)
            mgr.human_pause(1.5, 3.0)
            reason = mgr.check_block(page, "google")
            if reason:
                raise NeedsHumanError(reason)
            self._wait_for_articles(page)
            found: list[RawPlace] = []
            scrolls = 0
            while len(found) < max_results and scrolls < self.max_scrolls and not stop_event.is_set():
                articles = page.locator(self.item_selector)
                count = articles.count()
                if count == 0:
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(2000)
                    scrolls += 1
                    continue
                idx = 0
                while len(found) < max_results and idx < count:
                    first = articles.nth(idx)
                    if first.count() == 0:
                        break
                    key = str(first.get_attribute("data-cid") or first.get_attribute("place_id") or f"{idx}")
                    if key not in {p.source_id for p in found}:
                        raw = self._read_place(page, idx)
                        if raw is not None:
                            found.append(raw)
                    idx += 1
                mgr.human_pause(1.0, 2.5)
                page.mouse.wheel(0, 3000)
                scrolls += 1
                page.wait_for_timeout(1500)
            if not found:
                raise SourceChanged("google returned zero places")
            yield from found
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass

    def _read_place(self, page: Page, idx: int) -> RawPlace | None:  # noqa: ANN002
        article = page.locator(self.item_selector).nth(idx)
        if article.count() == 0:
            return None
        name = (article.get_attribute("data-name") or "").strip()
        address = (article.get_attribute("data-address") or "").strip()
        text = article.inner_text() or ""
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if not name and lines:
            name = lines[0]
        if not address and len(lines) > 1:
            address = ", ".join(lines[1:])
        if not name:
            return None
        return RawPlace(source="google", source_id=f"feed-{idx}", url="", name=name, address=address)
