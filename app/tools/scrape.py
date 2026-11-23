"""Scrape a source from the CLI: python -m app.tools.scrape <source> '<query>' --city '<city>' --max 20.

Prints a compact table plus coverage stats (percent with phone, website, rating, coordinates).
"""

from __future__ import annotations

import argparse
import sys

from app.browser.manager import BrowserManager
from app.logging_setup import setup_logging
from app.scrapers.base import BaseScraper
from app.scrapers.google import GoogleScraper


def get_scraper(source: str) -> BaseScraper:
    if source == "google":
        return GoogleScraper()
    raise ValueError(f"source {source} is not implemented yet (stage 3+)")


def run_scrape(source: str, query: str, city: str, max_results: int, country: str) -> int:
    setup_logging()
    scraper = get_scraper(source)
    manager = BrowserManager(headless=True)
    manager.start()
    if source == "google":
        scraper = GoogleScraper(manager=manager)
    stop_event = None
    places = []
    try:
        for place in scraper.iter_places(
            query=query,
            city=city,
            max_results=max_results,
            stop_event=stop_event,
            on_progress=lambda p, n: None,
        ):
            places.append(place)
    finally:
        manager.close()
    print(f"[scrape] source={source} query={query} city={city} found={len(places)}")
    with_phone = sum(1 for p in places if p.phones)
    with_site = sum(1 for p in places if p.website)
    with_rating = sum(1 for p in places if p.rating)
    with_geo = sum(1 for p in places if p.lat is not None and p.lon is not None)
    total = max(len(places), 1)
    print(f"[scrape] coverage phone={100 * with_phone / total:.0f}% website={100 * with_site / total:.0f}% rating={100 * with_rating / total:.0f}% geo={100 * with_geo / total:.0f}%")
    for p in places:
        print(f"[scrape] {p.name} | {p.address} | phones={p.phones} site={p.website} rating={p.rating} reviews={p.reviews_count} geo={p.lat},{p.lon}")
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Scrape places from a source into a compact table")
    ap.add_argument("source", choices=["google", "yandex", "twogis"])
    ap.add_argument("query")
    ap.add_argument("--city", default="Саратов")
    ap.add_argument("--country", default="Россия")
    ap.add_argument("--max", type=int, default=20)
    args = ap.parse_args(argv)
    if args.source != "google":
        print(f"[scrape] source {args.source} not implemented yet")
        return 2
    return run_scrape(args.source, args.query, args.city, args.max, args.country)


if __name__ == "__main__":
    raise SystemExit(main())
