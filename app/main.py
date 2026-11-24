"""FastAPI application entry: health, static files, routers."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.db import init_db
from app.logging_setup import setup_logging
from app.paths import STATIC_DIR, ensure_dirs


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    ensure_dirs()
    try:
        from app.db_backup import backup_db

        backup_db()
    except Exception:  # noqa: BLE001
        pass
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Zatsepka", version=__version__, lifespan=lifespan)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    from app.web.routes import api, misc, outreach, pages

    app.include_router(pages.router)
    app.include_router(api.router)
    app.include_router(outreach.router)
    app.include_router(misc.router)

    from app.hub.routes import router as hub_router

    app.include_router(hub_router)
    return app


app = create_app()
