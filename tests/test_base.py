"""Stage 7: export, filters, drawer API."""

from __future__ import annotations

import pytest

from app.db import session_scope
from app.models import Lead
from app.web.export import leads_csv, leads_xlsx


@pytest.mark.unit
def test_csv_has_bom_and_russian_headers():
    data = leads_csv([{"name": "Барбершоп", "city": "Саратов", "phones": ["+78452111111"]}])
    assert data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    assert "Название" in text
    assert "Барбершоп" in text


@pytest.mark.unit
def test_xlsx_generates(tmp_path):
    data = leads_xlsx([{"name": "Тест", "city": "Саратов"}])
    assert data[:2] == b"PK"
    p = tmp_path / "leads.xlsx"
    p.write_bytes(data)
    from openpyxl import load_workbook

    wb = load_workbook(p)
    assert wb.active["A1"].value == "Название"
    assert wb.active["A2"].value == "Тест"


@pytest.mark.integration
def test_export_endpoint(tmp_db):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with session_scope() as s:
        s.add(Lead(dedupe_key="k1", name="Тест", city="Саратов", status="in_base"))
    with TestClient(create_app()) as c:
        resp = c.post("/api/export", json={"format": "csv"})
        assert resp.status_code == 200
        assert "Тест" in resp.text


@pytest.mark.integration
def test_status_filter_endpoint(tmp_db):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with session_scope() as s:
        s.add(Lead(dedupe_key="a", name="Alpha", status="new"))
        s.add(Lead(dedupe_key="b", name="Beta", status="in_base"))
    with TestClient(create_app()) as c:
        r1 = c.get("/api/leads?tab=parser").json()
        r2 = c.get("/api/leads?tab=base").json()
        assert [x["name"] for x in r1] == ["Alpha"]
        assert [x["name"] for x in r2] == ["Beta"]
        r3 = c.post("/api/leads/bulk-status", json={"ids": [1], "status": "in_base"}).json()
        assert r3["updated"] == 1
