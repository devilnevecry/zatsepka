"""Live tests: real Saratov sources, skipped unless `pytest -m live`.

Nothing is sent to messengers; only local scraping and prompt/link generation.
"""

from __future__ import annotations

import pytest

from app.browser.manager import BrowserManager
from app.core.geo import scraper_for

CITY = "Саратов"
QUERY = "барбершоп"
SOURCES = ("google", "yandex", "twogis")


@pytest.mark.live
@pytest.mark.parametrize("source", SOURCES)
def test_live_source_rows(source):
    mgr = BrowserManager(headless=False)
    mgr.start()
    try:
        scraper = scraper_for(source, manager=mgr)
        places = []
        for place in scraper.iter_places(QUERY, CITY, 20, stop_event=None):
            places.append(place)
            if len(places) >= 20:
                break
        assert len(places) >= 1, f"{source}: no rows"
        with_name = sum(1 for p in places if p.name)
        with_phone = sum(1 for p in places if p.phones)
        with_site = sum(1 for p in places if p.website)
        with_rating = sum(1 for p in places if p.rating is not None)
        with_geo = sum(1 for p in places if p.lat is not None and p.lon is not None)
        print(
            f"[live] {source}: rows={len(places)} name={with_name} phone={with_phone} "
            f"site={with_site} rating={with_rating} geo={with_geo}"
        )
    finally:
        mgr.close()


@pytest.mark.live
def test_live_full_cycle(tmp_path, monkeypatch):
    """collect -> dedupe -> enrich -> prompt -> paste -> links -> mark sent (no outbound messenger calls)."""
    from app import config
    from app.core.jobs import JobRunner
    from app.db import session_scope
    from app.models import Lead

    monkeypatch.setenv("ROZVEDKA_DB", str(tmp_path / "live.db"))
    from app import db

    db.reset_engine_for_tests(tmp_path / "live.db")
    config.invalidate_cache()
    params = {
        "country": "Россия", "cities": [CITY], "categories": [QUERY], "sources": list(SOURCES),
        "max_results_per_pair": 20, "max_minutes": 20, "skip_days": 14,
        "no_repeat": False, "force": True, "enrich": True,
    }
    runner = JobRunner()
    job = runner.create_job(params)
    runner.start(job.id)
    assert runner.wait(job.id, timeout=600)
    job = runner.get_job(job.id)
    assert job.status == "done" and job.counters.get("found", 0) > 0
    with session_scope() as s:
        lead = s.query(Lead).first()
        assert lead is not None
        data = lead.to_dict()
        lead_id = lead.id
    with session_scope() as s:
        settings = config.get_settings(s)
    from app.ai.prompts import build_prompt
    from app.web.routes.outreach import channel_link

    prompt = build_prompt(data, settings, "telegram")
    assert data["name"] in prompt
    link = channel_link(data, "telegram", "Тестовое сообщение")
    assert link and "t.me" in link
    with session_scope() as s:
        from app.models import Message

        s.add(Message(lead_id=lead_id, channel="telegram", direction="out", text="Тестовое сообщение", status="sent"))
        lead = s.get(Lead, lead_id)
        lead.status = "waiting_reply"
    with session_scope() as s:
        assert s.get(Lead, lead_id).status == "waiting_reply"
    print(f"[live] full cycle OK: job={job.id} found={job.counters['found']} lead={lead_id} link={link}")
