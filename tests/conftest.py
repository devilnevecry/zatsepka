"""Shared fixtures: isolated temp database per test, clean settings cache."""

from __future__ import annotations

import pytest

from app import config
from app.db import reset_engine_for_tests, restore_engine


@pytest.fixture()
def tmp_db(tmp_path):
    config.invalidate_cache()
    engine = reset_engine_for_tests(tmp_path / "test.db")
    yield engine
    restore_engine()
    config.invalidate_cache()


@pytest.fixture()
def session(tmp_db):
    from app.db import session_scope

    with session_scope() as s:
        yield s
