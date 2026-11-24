"""Country/city geo resolution shared by all scrapers (SPEC 6: geo is global)."""

from __future__ import annotations

from urllib.parse import quote_plus

from app.scrapers.google import GoogleScraper
from app.scrapers.twogis import TwoGisScraper
from app.scrapers.yandex import YandexScraper


def resolve_url(source: str, query: str, city: str, country: str = "Россия", base_domains: dict | None = None) -> str:
    domains = base_domains or {"google": "google.com", "yandex": "yandex.ru", "twogis": "2gis.ru"}
    if source == "google":
        return f"https://www.{domains['google']}/maps/search/{quote_plus(query + ' ' + city)}?hl=ru"
    if source == "yandex":
        return f"https://{domains['yandex']}/maps/?text={quote_plus(query + ' ' + city)}"
    if source == "twogis":
        domain = (base_domains or {}).get("twogis", "2gis.ru")
        return f"https://{domain}/{TwoGisScraper.city_slug(city)}/search/{quote_plus(query)}"
    raise ValueError(f"unknown source {source}")


def scraper_for(source: str, manager=None, settings: dict | None = None):
    settings = settings or {}
    if source == "google":
        return GoogleScraper(manager=manager)
    if source == "yandex":
        return YandexScraper(manager=manager)
    if source == "twogis":
        return TwoGisScraper(manager=manager, base_domain=settings.get("base_domains", {}).get("twogis", "2gis.ru"))
    raise ValueError(f"unknown source {source}")
