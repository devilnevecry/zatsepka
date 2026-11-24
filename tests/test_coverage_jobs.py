"""Coverage: jobs edge paths + API surface."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.core.jobs import JobRunner
from app.db import session_scope
from app.main import create_app
from app.models import Job, JobPair, Lead
from app.scrapers.base import NeedsHuman, RawPlace


@pytest.mark.integration
def test_needs_human_pauses_and_continues(tmp_db):
    releases = []

    class Blocking:
        def __init__(self):
            self.called = False

        def iter_places(self, query, city, max_results, stop_event=None, on_progress=None):
            if not self.called:
                self.called = True
                releases.append(self)
                raise NeedsHuman("captcha")
            yield RawPlace(name="После капчи", phones=["+78452111111"])

    blocker = Blocking()
    runner = JobRunner(scraper_factory=lambda source, city: blocker)
    job = runner.create_job({
        "cities": ["Саратов"], "categories": ["барбершоп"], "sources": ["google"],
        "max_results_per_pair": 5, "no_repeat": False, "force": True,
    })
    runner.start(job.id)
    for _ in range(50):
        if releases:
            break
        time.sleep(0.05)
    assert releases
    runner.clear_human(job.id)
    assert runner.wait(job.id, timeout=15)
    assert runner.get_job(job.id).status == "done"
    with session_scope() as s:
        assert s.query(Lead).count() == 1


@pytest.mark.integration
def test_crash_resumes_pending_pairs(tmp_db):
    with session_scope() as s:
        job = Job(params={"cities": ["Саратов"], "categories": ["барбершоп"], "sources": ["google", "yandex"]}, status="running")
        s.add(job)
        s.flush()
        s.add(JobPair(job_id=job.id, city="Саратов", category="барбершоп", source="google", status="done", found=1))
        s.add(JobPair(job_id=job.id, city="Саратов", category="барбершоп", source="yandex", status="pending"))
        job_id = job.id
    runner = JobRunner(scraper_factory=lambda source, city: _one_place())
    runner.start(job_id)
    assert runner.wait(job_id, timeout=15)
    with session_scope() as s:
        pairs = s.query(JobPair).filter_by(job_id=job_id).order_by(JobPair.id).all()
        assert [p.status for p in pairs] == ["done", "done"]


def _one_place():
    class One:
        def iter_places(self, query, city, max_results, stop_event=None, on_progress=None):
            yield RawPlace(name="Resume Lead", phones=["+78452111111"])
    return One()


@pytest.mark.integration
def test_api_surface(tmp_db, monkeypatch):
    from app.web import state as web_state

    monkeypatch.setattr(web_state.runner, "scraper_factory", lambda source, city: _one_place())
    with TestClient(create_app()) as c:
        assert c.get("/api/settings").status_code == 200
        assert c.get("/api/estimate").status_code == 200
        assert c.get("/api/jobs/latest").status_code == 200
        assert c.get("/api/counts").status_code == 200
        assert c.get("/api/jobs/999").status_code == 200
        assert c.post("/api/jobs/999/pause").json()["ok"]
        assert c.post("/api/jobs/999/resume").json()["ok"]
        assert c.post("/api/jobs/999/stop").json()["ok"]
        r = c.post("/api/jobs", json={"cities": ["Саратов"], "categories": ["барбершоп"], "sources": {"google": False, "yandex": True, "twogis": False}, "force": True})
        assert "job_id" in r.json()
        c.post(f"/api/jobs/{r.json()['job_id']}/stop")
        assert c.get("/api/jobs/1").status_code == 200
        assert c.get("/api/prompts/template").status_code == 200


@pytest.mark.integration
def test_api_leads_and_templates(tmp_db):
    with session_scope() as s:
        s.add(Lead(dedupe_key="k1", name="Alpha", city="Саратов", status="new", website="https://example.ru", notes="old"))
    with TestClient(create_app()) as c:
        assert c.get("/api/leads/1").json()["name"] == "Alpha"
        assert c.post("/api/leads/1/notes", json={"notes": "new"}).json()["ok"]
        assert c.get("/api/leads/1").json()["notes"] == "new"
        assert c.post("/api/leads/enrich", json={"ids": []}).json()["ok"]
        assert c.post("/api/export", json={"format": "xlsx"}).status_code == 200
        assert c.request("DELETE", "/api/leads/bulk", json={"ids": [999]}).status_code == 200
        assert c.get("/api/templates").status_code == 200
        assert c.post("/api/templates", json={"name": "T", "body": "Привет {name}", "for_flag": ""}).json()["id"] > 0
        assert c.post("/api/templates/render", json={"body": "Привет {name}", "lead": {"name": "Alpha"}}).json()["text"] == "Привет Alpha"
        assert c.post("/api/prompts/template", json={"template": "{name} {bogus}"}).json()["unknown_variables"] == ["bogus"]
        assert c.post("/api/presets/save", json={"name": "Тест"}).json()["ok"]
        assert c.post("/api/messages/link", json={"lead": {"phones": ["+78452111111"]}, "channel": "call", "text": ""}).json()["url"] == "tel:+78452111111"


@pytest.mark.integration
def test_hub_api_surface(tmp_db, monkeypatch):
    from app.web import state as web_state

    monkeypatch.setattr(web_state.runner, "scraper_factory", lambda source, city: _one_place())
    with TestClient(create_app()) as c:
        assert c.post("/api/hub/modules/leads/start", json={}).json()["ok"] is True
        assert c.post("/api/hub/modules/leads/stop").json()["ok"]
        assert c.post("/api/hub/modules/hh/start", json={}).json()["ok"] is False
        assert c.post("/api/hub/modules/leads/queue").json()["items"]
        assert c.get("/api/hub/queue").status_code == 200
        assert c.post("/api/hub/queue/start").json()["ok"]
        assert c.get("/page/diagnostics").status_code == 200
