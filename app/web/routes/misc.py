"""Charts, profile, hotkeys and settings API."""

from __future__ import annotations

from fastapi import APIRouter, Body

from app.db import session_scope
from app.models import Lead, Message

router = APIRouter(prefix="/api")


@router.get("/charts")
def charts_api() -> dict:
    from app.web.charts import charts_data

    return charts_data()


@router.get("/profile/stats")
def profile_stats() -> dict:
    from app import config

    with session_scope() as s:
        settings = config.get_settings(s)
        return {
            "name": settings.get("profile_name", "Оператор"),
            "avatar": settings.get("profile_avatar", ""),
            "found": s.query(Lead).count(),
            "in_base": s.query(Lead).filter(Lead.status != "new").count(),
            "contacted": s.query(Lead).filter(Lead.status.in_(["contacted", "waiting_reply", "replied", "deal"])).count(),
            "replied": s.query(Lead).filter(Lead.status == "replied").count(),
            "messages": s.query(Message).count(),
        }


@router.get("/hotkeys")
def get_hotkeys() -> dict:
    from app import config

    with session_scope() as s:
        return config.get_settings(s).get("hotkeys", {})


@router.post("/hotkeys")
def save_hotkeys(body: dict = Body(...)) -> dict:
    from app import config

    with session_scope() as s:
        config.set_setting(s, "hotkeys", body)
    return {"ok": True}
