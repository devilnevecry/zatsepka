"""Capture tool: URL builders (unit) and clean about:blank run (integration)."""

from __future__ import annotations

import pytest

from app.tools.capture import search_url


@pytest.mark.unit
def test_search_urls():
    g = search_url("google", "барбершоп", "Саратов")
    assert g.startswith("https://www.google.com/maps/search/")
    assert "hl=ru" in g
    y = search_url("yandex", "барбершоп", "Саратов")
    assert y.startswith("https://yandex.ru/maps/?text=")
    t = search_url("twogis", "барбершоп", "Саратов")
    assert t == "https://2gis.ru/saratov/search/%D0%B1%D0%B0%D1%80%D0%B1%D0%B5%D1%80%D1%88%D0%BE%D0%BF"
    e = search_url("twogis", "кофейня", "Энгельс")
    assert "/engels/" in e


@pytest.mark.unit
def test_search_url_custom_domain():
    t = search_url("twogis", "барбершоп", "Саратов", domains={"twogis": "2gis.kz"})
    assert t.startswith("https://2gis.kz/")


@pytest.mark.integration
def test_capture_blank_exits_clean(tmp_path, monkeypatch):
    import app.browser.manager as manager_mod
    from app.tools.capture import run_capture

    monkeypatch.setattr(manager_mod, "BROWSER_PROFILE_DIR", tmp_path / "profile")
    monkeypatch.setattr(manager_mod, "BROWSER_LOCK_PATH", tmp_path / "browser.lock")
    code = run_capture("google", "тест", "Саратов", blank=True, headless=True, out_root=tmp_path / "cap")
    assert code == 0
    saved = list((tmp_path / "cap").rglob("results.html"))
    assert saved, "results.html must be saved even for about:blank"
    assert (saved[0].parent / "responses" / "responses.json").exists()
