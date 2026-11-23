"""Google scraper pure parsers (offline, against captured-shaped payloads)."""

from __future__ import annotations

import pytest

from app.scrapers.google import _norm_phone, parse_google_payload


def _make_place(name: str, address: str, phone: str = "+78452111222", rating: float = 4.5) -> dict:
    return {
        10: "ChIJplaceid123",
        11: name,
        39: address,
        78: "place-1",
        4: [None, None, None, None, None, None, None, rating, 128, None, None],
        7: [f"https://{name.replace(' ', '')}.example.com"],
        9: [None, None, 51.5, 45.8],
        37: [None, 12],
        13: ["BarberShop"],
        203: [[1, ["10:00", "20:00"]]],
        100: [None, []],
        161: [None, "Качественный барбершоп в центре."],
        178: [[None, None, None, phone]],
    }


def _make_payload(places: list[dict]) -> list:
    els: list[list] = []
    for p in places:
        els.append([None] * 14 + [p])
    page_key: list = [0] + els
    return [[None, page_key]]


@pytest.mark.unit
def test_parse_name_and_address():
    places = parse_google_payload(_make_payload([_make_place("Барбершоп Борода", "ул. Лермонтова, Саратов")]))
    assert len(places) == 1
    p = places[0]
    assert p.name == "Барбершоп Борода"
    assert p.address == "ул. Лермонтова, Саратов"
    assert p.source == "google"
    assert p.source_id == "ChIJplaceid123"


@pytest.mark.unit
def test_parse_phone_rating_reviews_website():
    p = parse_google_payload(_make_payload([_make_place("Барбершоп Борода", "ул. Лермонтова, Саратов", phone="+78452111222", rating=4.5)]))[0]
    assert p.phones == ["+78452111222"]
    assert p.rating == 4.5
    assert p.reviews_count == 128
    assert p.website.startswith("https://")
    assert "example.com" in p.website


@pytest.mark.unit
def test_parse_lat_lon_and_photos():
    p = parse_google_payload(_make_payload([_make_place("Барбершоп Борода", "Саратов", phone="+78452111222")]))[0]
    assert p.lat == 51.5
    assert p.lon == 45.8
    assert p.photos_count == 12


@pytest.mark.unit
def test_parse_empty_payload():
    assert parse_google_payload([]) == []
    assert parse_google_payload(None) == []


@pytest.mark.unit
def test_norm_phone_strips_non_digits():
    digits = _norm_phone("+7 (840) 211-11-22")
    assert digits == "+78402111122"
    assert digits.lstrip("+").isdigit()
    assert _norm_phone(None) == "+"


@pytest.mark.unit
def test_dedupe_key_uses_phone():
    p = parse_google_payload(_make_payload([_make_place("Барбершоп Борода", "Саратов")]))[0]
    assert p.to_lead_dedupe_key().startswith("tel:")
