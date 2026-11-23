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
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Rozvedka", version=__version__, lifespan=lifespan)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    from app.web.routes import pages

    app.include_router(pages.router)
    return app


app = create_app()
