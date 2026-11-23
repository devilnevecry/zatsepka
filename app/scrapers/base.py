"""Scraper contract: RawPlace, BaseScraper and errors (SPEC section 3)."""

from __future__ import annotations

import math
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.models import Lead  # noqa: F401  (type re-export convenience)


class ScrapesError(Exception):
    pass


class Stopped(ScrapesError):
    pass


class SourceChanged(ScrapesError):
    def __init__(self, details: str = "source returned no places"):
        super().__init__(details)
        self.details = details


class NeedsHuman(ScrapesError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class RawPlace(BaseModel):
    source: str = Field(default="google")
    source_id: str = Field(default="")
    url: str = Field(default="")
    name: str = Field(default="")
    category: str = ""
    address: str = ""
    lat: float | None = None
    lon: float | None = None
    phones: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    website: str = ""
    socials: dict[str, str] = Field(default_factory=dict)
    rating: float | None = None
    reviews_count: int | None = None
    description: str = ""
    hours: dict[str, str] = Field(default_factory=dict)
    attributes: list[str] = Field(default_factory=list)
    price_range: str = ""
    plus_code: str = ""
    photos_count: int | None = None
    top_reviews: list[dict] = Field(default_factory=list)
    extra: dict = Field(default_factory=dict)

    def to_lead_dedupe_key(self) -> str:
        phone = self.phones[0] if self.phones else ""
        if phone:
            return "tel:" + phone
        key = f"{self.name.casefold()}|{round(self.lat or 0, 3)}|{round(self.lon or 0, 3)}"
        return "geo:" + key


@dataclass
class ScrapedPlace:
    place: RawPlace
    detail: dict | None = None


@dataclass
class ListResult:
    places: list[ScrapedPlace] = field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


class BaseScraper:
    source: str = "google"
    max_scrolls: int = 60
    stop_event: threading.Event | None = None

    def iter_places(self, query: str, city: str, max_results: int, stop_event: threading.Event | None = None, on_progress=None) -> Iterator[RawPlace]:
        raise NotImplementedError

    def fetch_places(self, query: str, city: str, max_results: int, stop_event: threading.Event | None = None) -> list[RawPlace]:
        results: list[RawPlace] = []
        for place in self.iter_places(query, city, max_results, stop_event=stop_event):
            if stop_event is not None and stop_event.is_set():
                break
            results.append(place)
            if len(results) >= max_results:
                break
        return results


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_km(lat1, lon1, lat2, lon2) * 1000.0
