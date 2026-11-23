"""SQLAlchemy 2 (sync) setup: SQLite in WAL mode, schema bootstrap and versioning."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.paths import DB_PATH, ensure_dirs

SCHEMA_VERSION = 1


class Base(DeclarativeBase):
    pass


def _make_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return engine


def _db_path() -> Path:
    override = os.environ.get("ROZVEDKA_DB")
    return Path(override) if override else DB_PATH


engine: Engine = _make_engine(_db_path())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(eng: Engine | None = None) -> None:
    """Create all tables and record the schema version (idempotent)."""
    from app import models  # noqa: F401  (register mappers)

    target = eng or engine
    Base.metadata.create_all(target)
    with target.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"))
        row = conn.execute(text("SELECT version FROM schema_version LIMIT 1")).first()
        if row is None:
            conn.execute(text("INSERT INTO schema_version (version) VALUES (:v)"), {"v": SCHEMA_VERSION})
        elif row[0] != SCHEMA_VERSION:
            conn.execute(text("UPDATE schema_version SET version = :v"), {"v": SCHEMA_VERSION})


@contextmanager
def session_scope(eng: Engine | None = None) -> Iterator[Session]:
    factory = SessionLocal if eng is None else sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_tests(db_path: Path) -> Engine:
    """Point the module-level engine at a temporary database (tests only)."""
    global engine, SessionLocal
    engine.dispose()
    engine = _make_engine(db_path)
    SessionLocal.configure(bind=engine)
    init_db(engine)
    return engine


def restore_engine() -> None:
    global engine, SessionLocal
    engine.dispose()
    engine = _make_engine(_db_path())
    SessionLocal.configure(bind=engine)


ensure_dirs()
