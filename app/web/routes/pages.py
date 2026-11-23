"""Page routes. Stage 1: health-adjacent index stub; full UI lands in stage 6."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>РАЗВЕДКА</title></head>"
        "<body style='background:#0b0c10;color:#e8e9ee;font-family:system-ui'>"
        "<h1>РАЗВЕДКА</h1><p>Каркас запущен. Интерфейс появится на этапе 6.</p></body></html>"
    )
