"""Stage 11: registry, queue, supervisor, metrics, dashboard, diagnostics."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.hub.metrics import system_metrics
from app.hub.queue import ModuleQueue, _queue, _set_queue
from app.hub.registry import Module, Registry
from app.hub.supervisor import Supervisor
from app.main import create_app


@pytest.mark.unit
def test_registry():
    reg = Registry()
    reg.register(Module("leads", "Лиды", "🔍"))
    reg.register(Module("hh", "HH", "💼", available=False))
    assert [m.id for m in reg.all()] == ["leads", "hh"]
    assert reg.get("hh").safe_status() == "скоро"
    assert reg.get("leads").safe_status() == "stopped"


@pytest.mark.integration
def test_queue_order_and_persistence(tmp_db):
    started: list[str] = []
    q = ModuleQueue(start_fn=lambda mid, params: started.append(mid))
    q.enqueue("a")
    q.enqueue("b")
    assert [i["module_id"] for i in q.items()] == ["a", "b"]
    q.start()
    for _ in range(50):
        if len(started) == 2:
            break
        time.sleep(0.05)
    assert started == ["a", "b"]
    assert q.items() == []
    _set_queue([{"module_id": "c", "params": {}}])
    assert [i["module_id"] for i in _queue()] == ["c"]


@pytest.mark.unit
def test_supervisor_backoff():
    attempts = []

    def crash():
        attempts.append(time.time())
        raise RuntimeError("crash")

    sup = Supervisor()
    sup.register("fake", crash)
    sup.start("fake")
    time.sleep(3.5)
    sup.shutdown()
    assert len(attempts) >= 2
    assert sup.status("fake") in ("running", "stopped", "error")


@pytest.mark.unit
def test_metrics(monkeypatch):
    data = system_metrics()
    assert 0 <= data["cpu"] <= 100
    assert 0 <= data["ram"] <= 100
    assert 0 <= data["disk"] <= 100


@pytest.mark.integration
def test_dashboard_offline_ollama(tmp_db, monkeypatch):
    monkeypatch.setattr("app.hub.metrics.ollama_status", lambda url: {"available": False, "model": "", "vram": 0})
    with TestClient(create_app()) as c:
        assert c.get("/page/dashboard").status_code == 200
        metrics = c.get("/api/hub/metrics").json()
        assert metrics["ollama"]["available"] is False
        mods = c.get("/api/hub/modules").json()
        assert any(m["id"] == "leads" and m["available"] for m in mods)
        assert any(m["id"] == "hh" and not m["available"] for m in mods)
        assert c.get("/api/hub/diagnostics").status_code == 200
