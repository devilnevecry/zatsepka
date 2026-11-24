"""Yandex scraper pure parsers (offline)."""

from __future__ import annotations

import pytest

from app.scrapers.yandex import _norm_phone, parse_yandex_state


def _item(title: str = "Барбершоп Борода", address: str = "ул. Лермонтова, 1, Саратов") -> dict:
    return {
        "id": "12345",
        "title": title,
        "address": address,
        "compositeAddress": {"street": "ул. Лермонтова, 1"},
        "coordinates": [51.53, 46.03],
        "ratingData": {"ratingValue": 4.7, "ratingCount": 88},
        "workingTimeText": "пн-вс 10:00–22:00",
        "photos": {"count": 15},
        "categories": [{"name": "Барбершоп"}],
        "features": [{"name": "Парковка"}],
        "urls": ["https://barbershop.example.ru"],
        "phones": [{"value": "+78452111111"}],
        "socialLinks": [{"href": "https://t.me/barber"}],
    }


def _state(items: list[dict]) -> dict:
    return {"stack": [{"results": {"items": items}}]}


@pytest.mark.unit
def test_parse_name_address():
    places = parse_yandex_state(_state([_item()]))
    assert len(places) == 1
    assert places[0].name == "Барбершоп Борода"
    assert "Лермонтова" in places[0].address
    assert places[0].source == "yandex"
    assert places[0].source_id == "12345"


@pytest.mark.unit
def test_parse_contacts_and_rating():
    p = parse_yandex_state(_state([_item()]))[0]
    assert p.phones == ["+78452111111"]
    assert p.rating == 4.7
    assert p.reviews_count == 88
    assert p.website == "https://barbershop.example.ru"
    assert p.lat == 51.53
    assert p.lon == 46.03
    assert p.photos_count == 15
    assert "Барбершоп" in p.category
    assert "Парковка" in p.attributes[0]


@pytest.mark.unit
def test_parse_empty_state():
    assert parse_yandex_state({}) == []
    assert parse_yandex_state(None) == []


@pytest.mark.unit
def test_norm_phone():
    assert _norm_phone("+7 (845) 211-11-11") == "+78452111111"
