"""Coverage: geo, schemas, ollama, normalize, events, scraper parse edge cases."""

from __future__ import annotations

import pytest

from app.ai.ollama import ollama_status
from app.core.events import EventBus
from app.core.geo import resolve_url, scraper_for
from app.core.normalize import normalize_name, normalize_phone, normalize_socials, normalize_website
from app.schemas import EstimateOut, JobParams, LeadOut
from app.scrapers.google import parse_google_payload
from app.scrapers.twogis import parse_twogis_page_state, parse_twogis_payload
from app.scrapers.yandex import parse_yandex_state


@pytest.mark.unit
def test_geo_resolve_urls():
    assert "google.com/maps/search" in resolve_url("google", "барбершоп", "Саратов")
    assert "yandex.ru/maps/?text=" in resolve_url("yandex", "барбершоп", "Саратов")
    assert "2gis.ru/saratov/search/" in resolve_url("twogis", "барбершоп", "Саратов")
    assert "2gis.kz/engels" in resolve_url("twogis", "кофейня", "Энгельс", base_domains={"twogis": "2gis.kz"})
    with pytest.raises(ValueError):
        resolve_url("bing", "x", "Саратов")


@pytest.mark.unit
def test_geo_scraper_for():
    for source in ("google", "yandex", "twogis"):
        s = scraper_for(source, settings={"base_domains": {"twogis": "2gis.ru"}})
        assert s.source == source
    with pytest.raises(ValueError):
        scraper_for("bing")


@pytest.mark.unit
def test_schemas_defaults():
    j = JobParams()
    assert j.country == "Россия"
    assert j.cities == ["Саратов"]
    assert EstimateOut(pairs_total=1, pairs_skipped=0, pairs_to_run=1, approx_minutes=2.5).pairs_total == 1
    assert LeadOut(id=1, name="Тест").status == "new"


@pytest.mark.unit
def test_ollama_status_offline_and_online(monkeypatch):
    class Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"models": [{"name": "llama3", "size_vram": 1024}]}

    monkeypatch.setattr("app.ai.ollama.httpx.get", lambda url, timeout: Resp())
    assert ollama_status("http://127.0.0.1:11434") == {"available": True, "model": "llama3", "vram": 1024}
    monkeypatch.setattr("app.ai.ollama.httpx.get", lambda url, timeout: (_ for _ in ()).throw(OSError("down")))
    assert ollama_status("http://127.0.0.1:11434")["available"] is False


@pytest.mark.unit
def test_normalize_extras():
    assert normalize_website("example.ru/") == "https://example.ru"
    assert normalize_website("") == ""
    assert normalize_socials({"Telegram": "https://t.me/x", "empty": ""}) == {"telegram": "https://t.me/x"}
    assert normalize_socials(None) == {}
    assert normalize_phone("+7 845 211 11 11") == "+78452111111"
    assert normalize_phone("8452111111") == "+78452111111"
    assert normalize_phone("+1 202 555 0143", region="US").startswith("+1")
    assert normalize_name(None) == ""


@pytest.mark.unit
def test_event_bus_subscribe_publish():
    bus = EventBus()
    q = bus.subscribe(1)
    bus.publish(1, "progress", {"v": 1})
    item = q.get_nowait()
    assert item["event"] == "progress" and item["data"] == {"v": 1}
    bus.publish(99, "progress", {})  # no subscriber - safe
    chunks = list(bus.stream(1, timeout=0.05, max_events=2))
    assert any("event: done" in c or "keepalive" in c for c in chunks) or len(chunks) >= 1
    bus.unsubscribe(1)


@pytest.mark.unit
def test_parse_edge_cases():
    assert parse_google_payload({"not": "list"}) == []
    assert parse_google_payload([[None, [0, [None, []]]]]) == []
    assert parse_yandex_state({"stack": [{"results": {"items": [None, {}]}}]}) == []
    assert parse_twogis_payload({"result": {"items": [None, {}]}}) == []
    assert parse_twogis_page_state("<html>nothing</html>") == {}
