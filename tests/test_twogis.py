"""2GIS scraper pure parsers (offline, against captured fixture shapes)."""

from __future__ import annotations

import pytest

from app.scrapers.twogis import TwoGisScraper, _norm_phone, parse_twogis_payload


def _item() -> dict:
    return {
        "id": "70000001027500523",
        "name": "Барбершоп Борода",
        "address_name": "улица Большая Казачья, 69/73",
        "rubrics": [{"name": "Барбершоп"}],
        "point": {"lat": 51.532, "lon": 46.03},
        "contact_groups": [
            {"contacts": [
                {"type": "phone", "text": "+7 (845) 211-11-11"},
                {"type": "email", "text": "info@example.ru"},
                {"type": "website", "text": "https://example.ru"},
            ]}
        ],
        "reviews": {"general_rating": 4.6, "general_review_count": 120},
        "attribute_groups": [{"attributes": [{"name": "Парковка"}]}],
    }


@pytest.mark.unit
def test_parse_fields():
    places = parse_twogis_payload({"result": {"items": [_item()]}})
    assert len(places) == 1
    p = places[0]
    assert p.name == "Барбершоп Борода"
    assert p.address == "улица Большая Казачья, 69/73"
    assert p.phones == ["+78452111111"]
    assert p.emails == ["info@example.ru"]
    assert p.website == "https://example.ru"
    assert p.rating == 4.6
    assert p.reviews_count == 120
    assert p.lat == 51.532
    assert "Парковка" in p.attributes
    assert "2gis.ru" in p.url


@pytest.mark.unit
def test_parse_empty():
    assert parse_twogis_payload({}) == []
    assert parse_twogis_payload(None) == []


@pytest.mark.unit
def test_city_slug():
    assert TwoGisScraper.city_slug("Саратов") == "saratov"
    assert TwoGisScraper.city_slug("Энгельс") == "engels"


@pytest.mark.unit
def test_norm_phone():
    assert _norm_phone("+7 (845) 211-11-11") == "+78452111111"
