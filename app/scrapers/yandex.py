"""Yandex Maps scraper: pure parsers + thin browser layer (stage 3)."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from typing import Any

from playwright.sync_api import Page

from app.browser.manager import BrowserManager, NeedsHumanError
from app.scrapers.base import BaseScraper, RawPlace, SourceChanged


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm_phone(raw: Any) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return "+" + digits


def parse_yandex_state(state: Any) -> list[RawPlace]:  # noqa: ANN001, ANN202
    """Parse a Yandex maps org item state into a RawPlace (pure fn).

    Shape (from GeoLeadScraper hints + captured fixtures): state.stack[0].results.items[]
    with title, address/compositeAddress, coordinates, ratingData, workingTimeText, photos,
    categories, features, urls, phones, socialLinks.
    """
    out: list[RawPlace] = []
    root = _as_dict(state)
    stack = _as_list(root.get("stack"))
    items: list[dict] = []
    if stack and isinstance(stack[0], dict):
        results = _as_dict(stack[0].get("results"))
        items = _as_list(results.get("items"))
    for item in items:
        place_data = item if isinstance(item, dict) else {}
        nested = place_data.get("result")
        if isinstance(nested, dict):
            place_data = nested
        if not place_data:
            continue
        title = str(place_data.get("title") or "")
        composite = _as_dict(place_data.get("compositeAddress"))
        street = str(composite.get("street") or "")
        address_parts = [street, str(place_data.get("address") or ""), str(place_data.get("city") or "")]
        address = ", ".join(p for p in address_parts if p)
        coords = _as_list(place_data.get("coordinates"))
        lat = float(coords[0]) if len(coords) > 0 else None
        lon = float(coords[1]) if len(coords) > 1 else None
        rating_data = _as_dict(place_data.get("ratingData"))
        rating = float(rating_data.get("ratingValue")) if rating_data.get("ratingValue") is not None else None
        review_count = int(rating_data.get("ratingCount") or 0) if rating_data.get("ratingCount") is not None else None
        photos = place_data.get("photos")
        photos_count = int(photos.get("count")) if isinstance(photos, dict) and photos.get("count") is not None else None
        categories = ", ".join(str(c.get("name")) for c in _as_list(place_data.get("categories")) if isinstance(c, dict) and c.get("name"))
        features = ", ".join(str(f.get("name")) for f in _as_list(place_data.get("features")) if isinstance(f, dict) and f.get("name"))
        urls = _as_list(place_data.get("urls"))
        website = str(urls[0]) if urls else ""
        phones_raw = _as_list(place_data.get("phones"))
        phone = ""
        socials: dict[str, str] = {}
        if phones_raw and phones_raw[0]:
            phone = _norm_phone(phones_raw[0].get("value"))
        social_list = _as_list(place_data.get("socialLinks"))
        for s in social_list:
            if isinstance(s, dict) and s.get("href"):
                key = str(s.get("href"))
                socials[key] = key
        hours = {"workingTime": str(place_data.get("workingTimeText") or "")}
        out.append(
            RawPlace(
                source="yandex",
                source_id=str(place_data.get("id") or ""),
                url=str(urls[0] or f"https://yandex.ru/maps/?text={title}") if urls else f"https://yandex.ru/maps/?text={title}",
                name=title,
                category=categories,
                address=address,
                lat=lat,
                lon=lon,
                phones=[phone] if phone else [],
                emails=[],
                website=website,
                socials=socials,
                rating=rating,
                reviews_count=review_count,
                description="",
                hours=hours,
                attributes=[features] if features else [],
                price_range="",
                plus_code="",
                photos_count=photos_count,
                top_reviews=[],
                extra={"features": features},
            )
        )
    return out


class YandexScraper(BaseScraper):
    source = "yandex"
    list_container = ".search-list-view__list"
    scroller = ".scroll__container"
    item_selector = 'a[href*="/maps/org/"]'

    def __init__(self, manager: BrowserManager | None = None):
        super().__init__()
        self.manager = manager or BrowserManager(headless=True)

    def _wait_for_items(self, page: Page, timeout_ms: int = 60000) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if page.locator(self.item_selector).count() > 0:
                return
            page.wait_for_timeout(500)
        raise SourceChanged("no result items appeared in the yandex list")

    def iter_places(self, query: str, city: str, max_results: int, stop_event: threading.Event | None = None, on_progress=None) -> Iterator[RawPlace]:
        if stop_event is None:
            stop_event = threading.Event()
        mgr = self.manager
        page = mgr.new_page()
        try:
            url = f"https://yandex.ru/maps/?text={query.replace(' ', '+')}+{city.replace(' ', '+')}"
            mgr.goto(page, url)
            mgr.human_pause(1.5, 3.0)
            reason = mgr.check_block(page, "yandex")
            if reason:
                raise NeedsHumanError(reason)
            self._wait_for_items(page)
            found: list[RawPlace] = []
            scrolls = 0
            scroller = page.locator(self.scroller).first
            while len(found) < max_results and scrolls < self.max_scrolls and not stop_event.is_set():
                items = page.locator(self.item_selector)
                count = items.count()
                if count == 0:
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(2000)
                    scrolls += 1
                    continue
                # read first max_results items
                idx = 0
                while len(found) < max_results and idx < count:
                    item = items.nth(idx)
                    if item.count() == 0:
                        break
                    href = str(item.get_attribute("href") or "")
                    if not href.startswith("/maps/org/") or any(x in href for x in ("/reviews", "/gallery")):
                        idx += 1
                        continue
                    if href in {p.url for p in found}:
                        idx += 1
                        continue
                    data = item.evaluate(
                        """el => {
                            const card = el.closest('[class]') || el.parentElement;
                            const txt = (el.innerText || '').trim();
                            const href = el.getAttribute('href') || '';
                            return { text: txt, href: href, card: card ? card.innerText : txt };
                        }"""
                    )
                    name = str(data.get("text") or "").split("\n")[0].strip()
                    address = str(data.get("card") or str(data.get("text") or ""))[:200]
                    if name:
                        found.append(RawPlace(source="yandex", source_id=f"org-{idx}", url=str(data.get("href") or ""), name=name, address=address))
                    idx += 1
                mgr.human_pause(1.0, 2.5)
                if scroller.count():
                    page.evaluate("el => { el.scrollTop = el.scrollTop + 3000 }", scroller.first.element_handle())
                scrolls += 1
                page.wait_for_timeout(1500)
            if not found:
                raise SourceChanged("yandex returned zero places")
            yield from found
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
