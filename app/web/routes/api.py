"""JSON/SSE API routes for the UI."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Request
from fastapi.responses import StreamingResponse

from app import config
from app.core.events import event_bus
from app.core.jobs import JobRunner, estimate
from app.db import session_scope
from app.models import Job, Lead, Message

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def _runner() -> JobRunner:
    from app.web.state import runner

    return runner


@router.get("/settings")
def get_settings_api() -> dict:
    with session_scope() as s:
        return config.get_settings(s)


@router.post("/settings")
def update_settings_api(values: dict = Body(...)) -> dict:
    with session_scope() as s:
        return config.update_settings(s, values)


@router.get("/estimate")
def estimate_api() -> dict:
    with session_scope() as s:
        return estimate(s, config.get_settings(s))


@router.post("/jobs")
def start_job_api(params: dict = Body(default_factory=dict)) -> dict:
    with session_scope() as s:
        settings = config.get_settings(s)
    merged = dict(settings)
    merged.update(params or {})
    merged["sources"] = [k for k, v in merged.get("sources", {}).items() if v] if isinstance(merged.get("sources"), dict) else merged.get("sources", [])
    job = _runner().create_job(merged)
    _runner().start(job.id)
    return {"job_id": job.id, "status": "running"}


@router.get("/jobs/latest")
def latest_job_api() -> dict:
    with session_scope() as s:
        job = s.query(Job).order_by(Job.id.desc()).first()
        if not job:
            return {"id": None, "status": None, "counters": {}, "params": {}}
        return {"id": job.id, "status": job.status, "counters": job.counters or {}, "params": job.params or {}}


@router.get("/jobs/{job_id}")
def job_api(job_id: int) -> dict:
    with session_scope() as s:
        job = s.get(Job, job_id)
        if not job:
            return {"id": job_id, "status": None}
        return {"id": job.id, "status": job.status, "counters": job.counters or {}}


@router.post("/jobs/{job_id}/pause")
def pause_job_api(job_id: int) -> dict:
    _runner().pause(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/resume")
def resume_job_api(job_id: int) -> dict:
    _runner().resume(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/stop")
def stop_job_api(job_id: int) -> dict:
    _runner().stop(job_id)
    return {"ok": True}


@router.get("/jobs/{job_id}/events")
def job_events(job_id: int, request: Request):
    def gen():
        yield from event_bus.stream(job_id)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/leads")
def leads_api(tab: str = "parser", search: str = "", city: str = "", status: str = "", limit: int = 500) -> list[dict]:
    with session_scope() as s:
        q = s.query(Lead)
        if tab == "parser":
            latest = s.query(Job).order_by(Job.id.desc()).first()
            q = q.filter(Lead.status == "new")
            if latest:
                q = q.filter(Lead.job_id == latest.id)
        elif tab == "base":
            q = q.filter(Lead.status != "new")
        elif tab == "messages":
            ids = [m.lead_id for m in s.query(Message).all()]
            q = q.filter(Lead.id.in_(ids))
        if search:
            from sqlalchemy import or_

            like = f"%{search}%"
            q = q.filter(or_(Lead.name.like(like), Lead.address.like(like), Lead.category.like(like)))
        if city:
            q = q.filter(Lead.city == city)
        if status:
            q = q.filter(Lead.status == status)
        leads = q.order_by(Lead.id.desc()).limit(limit).all()
        return [lead.to_dict() for lead in leads]


@router.get("/leads/{lead_id}")
def lead_api(lead_id: int) -> dict:
    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        if not lead:
            return {}
        return lead.to_dict()


@router.get("/counts")
def counts_api() -> dict:
    with session_scope() as s:
        latest = s.query(Job).order_by(Job.id.desc()).first()
        parser = s.query(Lead).filter(Lead.status == "new")
        if latest:
            parser = parser.filter(Lead.job_id == latest.id)
        return {
            "parser": parser.count(),
            "base": s.query(Lead).filter(Lead.status != "new").count(),
            "messages": len({m.lead_id for m in s.query(Message).all()}),
        }


@router.post("/leads/{lead_id}/status")
def set_lead_status(lead_id: int, body: dict = Body(...)) -> dict:
    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        if lead:
            lead.status = str(body.get("status", lead.status))
            return lead.to_dict()
    return {}


@router.post("/leads/bulk-status")
def bulk_status(body: dict = Body(...)) -> dict:
    ids = body.get("ids") or []
    status = body.get("status", "in_base")
    with session_scope() as s:
        for lead_id in ids:
            lead = s.get(Lead, int(lead_id))
            if lead:
                lead.status = status
    return {"ok": True, "updated": len(ids)}


@router.delete("/leads/bulk")
def bulk_delete(body: dict = Body(...)) -> dict:
    ids = body.get("ids") or []
    with session_scope() as s:
        for lead_id in ids:
            lead = s.get(Lead, int(lead_id))
            if lead:
                s.delete(lead)
    return {"ok": True, "deleted": len(ids)}


@router.post("/leads/{lead_id}/notes")
def save_notes(lead_id: int, body: dict = Body(...)) -> dict:
    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        if lead:
            lead.notes = str(body.get("notes", lead.notes))
            return {"ok": True}
    return {"ok": False}
