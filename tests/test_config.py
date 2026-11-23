"""Settings defaults, persistence and cache invalidation."""

from __future__ import annotations

import pytest

from app import config


@pytest.mark.unit
def test_defaults_match_spec(session):
    s = config.get_settings(session)
    assert s["country"] == "Россия"
    assert s["cities"] == ["Саратов"]
    assert s["phone_region"] == "RU"
    assert s["skip_days"] == 14
    assert s["max_results_per_pair"] == 60
    assert s["max_minutes"] == 60
    assert s["base_domains"]["twogis"] == "2gis.ru"
    assert s["sources"] == {"google": True, "yandex": True, "twogis": True}


@pytest.mark.unit
def test_set_and_read_back(session):
    config.set_setting(session, "cities", ["Саратов", "Энгельс"])
    config.invalidate_cache()
    s = config.get_settings(session)
    assert s["cities"] == ["Саратов", "Энгельс"]


@pytest.mark.unit
def test_update_ignores_unknown_keys(session):
    config.update_settings(session, {"skip_days": 7, "bogus_key": 1})
    s = config.get_settings(session)
    assert s["skip_days"] == 7
    assert "bogus_key" not in s


@pytest.mark.unit
def test_returned_settings_are_copies(session):
    s1 = config.get_settings(session)
    s1["cities"].append("Энгельс")
    s2 = config.get_settings(session)
    assert s2["cities"] == ["Саратов"]
