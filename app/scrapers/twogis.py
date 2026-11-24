"""2GIS scraper: pure parsers + thin browser layer (stage 4)."""

from __future__ import annotations

import re
import threading
from collections.abc import Iterator
from typing import Any

from app.browser.manager import BrowserManager, NeedsHumanError
from app.scrapers.base import BaseScraper, RawPlace, SourceChanged


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm_phone(raw: Any) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return "+" + digits


def parse_twogis_payload(payload: Any, base_domain: str = "2gis.ru") -> list[RawPlace]:  # noqa: ANN001, ANN202
    """Parse catalog items (result.items each exposing contact_groups etc)."""
    if not isinstance(payload, dict):
        return []
    result = _as_dict(payload.get("result"))
    items = _as_list(result.get("items"))
    out: list[RawPlace] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        phones: list[str] = []
        emails: list[str] = []
        website = ""
        socials: dict[str, str] = {}
        for group in _as_list(item.get("contact_groups")):
            for contact in _as_list(_as_dict(group).get("contacts")):
                c = _as_dict(contact)
                text = str(c.get("text") or "")
                ctype = str(c.get("type") or "")
                if ctype == "phone" and text:
                    phones.append(_norm_phone(text))
                elif ctype == "email" and text:
                    emails.append(text)
                elif ctype == "website" and text and not website:
                    website = text
                elif ctype == "social" and text:
                    socials[str(c.get("slug") or "social")] = text
        rating = item.get("rating") or _as_dict(item.get("reviews")).get("general_rating")
        reviews = _as_dict(item.get("reviews")).get("general_review_count")
        point = _as_dict(item.get("point"))
        categories = ", ".join(str(r.get("name")) for r in _as_list(item.get("rubrics")) if isinstance(r, dict) and r.get("name"))
        attributes: list[str] = []
        for group in _as_list(item.get("attribute_groups")):
            for attr in _as_list(_as_dict(group).get("attributes")):
                if isinstance(attr, dict) and attr.get("name"):
                    attributes.append(str(attr["name"]))
        out.append(
            RawPlace(
                source="twogis",
                source_id=str(item.get("id") or ""),
                url=f"https://{base_domain}/firm/{item.get('id') or ''}",
                name=name,
                category=categories,
                address=str(item.get("address_name") or ""),
                lat=float(point["lat"]) if isinstance(point.get("lat"), (int, float)) else None,
                lon=float(point["lon"]) if isinstance(point.get("lon"), (int, float)) else None,
                phones=phones,
                emails=emails,
                website=website,
                socials=socials,
                rating=float(rating) if isinstance(rating, (int, float)) else None,
                reviews_count=int(reviews) if isinstance(reviews, (int, float)) else None,
                description=str(item.get("description") or ""),
                hours={},
                attributes=attributes,
                price_range=str(item.get("price_range") or ""),
                photos_count=int(item["external_content"][0]["count"]) if _as_list(item.get("external_content")) and _as_dict(_as_list(item.get("external_content"))[0]).get("count") is not None else None,
                top_reviews=[],
                extra={"city": str(item.get("city") or "")},
            )
        )
    return out


def parse_twogis_page_state(html: str) -> dict:
    """Extract embedded initialState JSON from a 2GIS page (pure fn)."""
    import json

    match = re.search(r"var\s+initialState\s*=\s*JSON\.parse\('([\s\S]*?)'\)\s*;", html)
    if not match:
        m2 = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>([\s\S]*?)</script>', html)
        if m2:
            try:
                return json.loads(m2.group(1))
            except json.JSONDecodeError:
                return {}
        return {}
    raw = "{" + match.group(1) + "}"
    raw = raw.replace('\\"', '"')
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


class TwoGisScraper(BaseScraper):
    source = "twogis"
    list_selector = "a[href*='/firm/']"

    def __init__(self, manager: BrowserManager | None = None, base_domain: str = "2gis.ru"):
        super().__init__()
        self.manager = manager or BrowserManager(headless=True)
        self.base_domain = base_domain

    @staticmethod
    def city_slug(city: str) -> str:
        return {"саратов": "saratov", "энгельс": "engels"}.get(city.casefold(), city.casefold())

    def iter_places(self, query: str, city: str, max_results: int, stop_event: threading.Event | None = None, on_progress=None) -> Iterator[RawPlace]:
        if stop_event is None:
            stop_event = threading.Event()
        mgr = self.manager
        page = mgr.new_page()
        try:
            url = f"https://{self.base_domain}/{self.city_slug(city)}/search/{query.replace(' ', '%20')}"
            mgr.goto(page, url)
            mgr.human_pause(1.5, 3.0)
            reason = mgr.check_block(page, "twogis")
            if reason:
                raise NeedsHumanError(reason)
            found: list[RawPlace] = []
            scrolls = 0
            seen: set[str] = set()
            while len(found) < max_results and scrolls < self.max_scrolls and not stop_event.is_set():
                anchors = page.locator(self.list_selector)
                count = anchors.count()
                idx = 0
                while len(found) < max_results and idx < count:
                    href = str(anchors.nth(idx).get_attribute("href") or "")
                    if "/firm/" in href and href not in seen:
                        seen.add(href)
                        title = str(anchors.nth(idx).inner_text() or "").strip()
                        if title:
                            found.append(RawPlace(source="twogis", source_id=href, url=href, name=title))
                    idx += 1
                page.evaluate(
                    """() => {
                        const a = document.querySelector("a[href*='/firm/']");
                        if (!a) { window.scrollBy(0, 2500); return; }
                        let el = a.parentElement;
                        while (el && el !== document.body) {
                            const st = getComputedStyle(el);
                            if ((st.overflowY === 'auto' || st.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 50) {
                                el.scrollTop = el.scrollTop + 2500;
                                return;
                            }
                            el = el.parentElement;
                        }
                        window.scrollBy(0, 2500);
                    }"""
                )
                scrolls += 1
                mgr.human_pause(1.0, 2.5)
                page.wait_for_timeout(2000)
            if not found:
                raise SourceChanged("twogis returned zero places")
            yield from found
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
