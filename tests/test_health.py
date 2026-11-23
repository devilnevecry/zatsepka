"""Health endpoint and app factory."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_health_ok(tmp_db):
    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


@pytest.mark.unit
def test_index_stub(tmp_db):
    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "РАЗВЕДКА" in resp.text
