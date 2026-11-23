"""DB bootstrap: tables, WAL mode, schema version."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

from app.db import init_db, session_scope


@pytest.mark.unit
def test_init_creates_all_tables(tmp_db):
    init_db(tmp_db)
    names = set(inspect(tmp_db).get_table_names())
    expected = {"leads", "jobs", "job_pairs", "pair_history", "messages", "templates", "settings", "schema_version"}
    assert expected <= names


@pytest.mark.unit
def test_wal_mode_enabled(tmp_db):
    with tmp_db.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert mode.lower() == "wal"


@pytest.mark.unit
def test_schema_version_recorded(tmp_db):
    init_db(tmp_db)
    init_db(tmp_db)  # idempotent
    with tmp_db.connect() as conn:
        rows = conn.execute(text("SELECT version FROM schema_version")).all()
    assert len(rows) == 1
    assert rows[0][0] >= 1


@pytest.mark.unit
def test_lead_roundtrip(tmp_db):
    from app.models import Lead

    with session_scope() as s:
        lead = Lead(dedupe_key="k1", name="Тест", city="Саратов", phones=["+78452000000"], socials={"vk": "https://vk.com/x"})
        s.add(lead)
    with session_scope() as s:
        got = s.query(Lead).filter_by(dedupe_key="k1").one()
        assert got.phones == ["+78452000000"]
        assert got.socials["vk"] == "https://vk.com/x"
        assert got.status == "new"
        d = got.to_dict()
        assert d["city"] == "Саратов"
