"""Stage 10: charts, settings, profile, hotkeys."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import session_scope
from app.main import create_app
from app.models import Lead, Message


@pytest.mark.integration
def test_settings_persist_without_restart(tmp_db):
    with TestClient(create_app()) as c:
        r = c.post("/api/settings", json={"skip_days": 7, "phone_region": "RU"})
        assert r.status_code == 200
        assert c.get("/api/settings").json()["skip_days"] == 7
    with TestClient(create_app()) as c:
        assert c.get("/api/settings").json()["skip_days"] == 7


@pytest.mark.integration
def test_charts_and_profile(tmp_db):
    with session_scope() as s:
        s.add(Lead(dedupe_key="a", name="A", city="Саратов", category="барбершоп", status="new"))
        s.add(Lead(dedupe_key="b", name="B", city="Энгельс", category="кофейня", status="replied"))
        s.add(Message(lead_id=2, channel="telegram", text="ok", status="sent"))
    with TestClient(create_app()) as c:
        data = c.get("/api/charts").json()
        assert dict(data["funnel"])["new"] == 1
        assert dict(data["top_cities"])["Саратов"] == 1
        stats = c.get("/api/profile/stats").json()
        assert stats["found"] == 2 and stats["replied"] == 1
        assert c.get("/page/charts").status_code == 200
        assert c.get("/page/settings").status_code == 200
        assert c.get("/page/help").status_code == 200


@pytest.mark.unit
def test_hotkeys_default_and_rebind(tmp_db):
    with TestClient(create_app()) as c:
        keys = c.get("/api/hotkeys").json()
        assert keys["focus_search"] == "/"
        c.post("/api/hotkeys", json={**keys, "add_to_base": "n"})
        assert c.get("/api/hotkeys").json()["add_to_base"] == "n"
