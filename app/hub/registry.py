"""Module registry per SPEC 9."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Module:
    id: str
    title: str
    icon: str
    start: Callable | None = None
    stop: Callable | None = None
    status: Callable | None = None
    available: bool = True
    params: dict[str, Any] = field(default_factory=dict)

    def safe_status(self) -> str:
        if not self.available:
            return "скоро"
        if self.status is None:
            return "stopped"
        try:
            return str(self.status())
        except Exception:  # noqa: BLE001
            return "error"


class Registry:
    def __init__(self):
        self._modules: dict[str, Module] = {}

    def register(self, module: Module) -> None:
        self._modules[module.id] = module

    def get(self, module_id: str) -> Module | None:
        return self._modules.get(module_id)

    def all(self) -> list[Module]:
        return list(self._modules.values())


registry = Registry()


def _register_builtins() -> None:
    from app.web.state import runner

    def leads_status() -> str:
        from app.db import session_scope
        from app.models import Job

        with session_scope() as s:
            job = s.query(Job).order_by(Job.id.desc()).first()
            return job.status if job else "stopped"

    def leads_start(params: dict | None = None) -> dict:
        from app import config
        from app.db import session_scope

        with session_scope() as s:
            settings = config.get_settings(s)
        merged = dict(settings)
        merged.update(params or {})
        merged["sources"] = [k for k, v in merged.get("sources", {}).items() if v] if isinstance(merged.get("sources"), dict) else merged.get("sources", [])
        job = runner.create_job(merged)
        runner.start(job.id)
        return {"job_id": job.id}

    def leads_stop() -> dict:
        from app.db import session_scope
        from app.models import Job

        with session_scope() as s:
            job = s.query(Job).order_by(Job.id.desc()).first()
            if job:
                runner.stop(job.id)
        return {"ok": True}

    registry.register(Module("leads", "Разведка лидов", "🔍", leads_start, leads_stop, leads_status))
    for mid, title, icon in (
        ("hh", "HeadHunter", "💼"),
        ("habr", "Хабр", "🅿"),
        ("freelance", "Фриланс", "🧩"),
    ):
        registry.register(Module(mid, title, icon, available=False))


_register_builtins()
