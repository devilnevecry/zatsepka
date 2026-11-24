"""Hub API: module cards, queue, metrics, log tail SSE."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from app.hub.registry import registry
from app.logging_setup import setup_logging
from app.paths import LOGS_DIR

router = APIRouter(prefix="/api/hub")


def _queue():
    from app.hub.queue import ModuleQueue

    return ModuleQueue(registry=registry, start_fn=_start_module)


def _start_module(module_id: str, params: dict) -> None:
    module = registry.get(module_id)
    if module and module.start:
        module.start(params)


@router.get("/modules")
def modules_api() -> list[dict]:
    out = []
    for m in registry.all():
        out.append({
            "id": m.id,
            "title": m.title,
            "icon": m.icon,
            "available": m.available,
            "status": m.safe_status(),
        })
    return out


@router.post("/modules/{module_id}/start")
def start_module_api(module_id: str, body: dict = Body(default_factory=dict)) -> dict:
    module = registry.get(module_id)
    if module is None or not module.available or module.start is None:
        return {"ok": False}
    module.start(body or {})
    return {"ok": True}


@router.post("/modules/{module_id}/stop")
def stop_module_api(module_id: str) -> dict:
    module = registry.get(module_id)
    if module and module.stop:
        module.stop()
    return {"ok": True}


@router.post("/modules/{module_id}/queue")
def queue_module_api(module_id: str) -> dict:
    return {"items": _queue().enqueue(module_id)}


@router.get("/queue")
def queue_api() -> list[dict]:
    return _queue().items()


@router.post("/queue/start")
def queue_start_api() -> dict:
    q = _queue()
    q.start()
    return {"ok": True}


@router.get("/metrics")
def metrics_api() -> dict:
    from app.hub.metrics import ollama_card, system_metrics

    return {**system_metrics(), "ollama": ollama_card()}


@router.get("/logs/{module_id}")
def log_tail(module_id: str, level: str = "INFO", lines: int = 200):
    setup_logging()
    path = LOGS_DIR / f"{module_id}.log"
    if not path.exists():
        path = LOGS_DIR / "app.log"

    def gen():
        idle = 0
        while idle < 60:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                selected = [ln for ln in content.splitlines()[-lines:] if level.upper() in ln.upper()] if level else content.splitlines()[-lines:]
                yield f"data: {__import__('json').dumps({'lines': selected}, ensure_ascii=False)}\n\n"
            except OSError:
                pass
            idle += 1
            if idle % 6 == 0:
                yield ": keepalive\n\n"
            time.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/diagnostics")
def diagnostics_api() -> list[dict]:
    from app.db import session_scope
    from app.models import JobPair

    with session_scope() as s:
        rows = s.query(JobPair).filter(JobPair.status == "failed").order_by(JobPair.id.desc()).limit(100).all()
        return [
            {
                "job_id": r.job_id,
                "city": r.city,
                "category": r.category,
                "source": r.source,
                "error": r.error,
                "snapshot": str(Path("debug") / "capture" / r.source),
            }
            for r in rows
        ]
