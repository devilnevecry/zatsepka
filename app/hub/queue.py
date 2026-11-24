"""Persistent sequential module queue (SPEC 9)."""

from __future__ import annotations

import threading
import time

from app.db import session_scope
from app.models import Setting


def _queue() -> list[dict]:
    with session_scope() as s:
        row = s.get(Setting, "hub_queue")
        return list(row.value) if row and isinstance(row.value, list) else []


def _set_queue(items: list[dict]) -> None:
    with session_scope() as s:
        row = s.get(Setting, "hub_queue")
        if row is None:
            from app.models import Setting as SettingModel

            row = SettingModel(key="hub_queue", value=items)
            s.add(row)
        else:
            row.value = items


class ModuleQueue:
    def __init__(self, registry=None, start_fn=None):
        self.registry = registry
        self.start_fn = start_fn
        self._running = False
        self._thread: threading.Thread | None = None

    def enqueue(self, module_id: str, params: dict | None = None) -> list[dict]:
        items = _queue()
        items.append({"module_id": module_id, "params": params or {}})
        _set_queue(items)
        return items

    def items(self) -> list[dict]:
        return _queue()

    def clear(self) -> None:
        _set_queue([])

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="hub-queue")
        self._thread.start()

    def _run(self) -> None:
        max_cycles = 1000
        cycles = 0
        while self._running and cycles < max_cycles:
            cycles += 1
            items = _queue()
            if not items:
                break
            item = items.pop(0)
            _set_queue(items)
            try:
                if self.start_fn:
                    self.start_fn(item["module_id"], item.get("params") or {})
                elif self.registry:
                    module = self.registry.get(item["module_id"])
                    if module and module.start:
                        module.start(item.get("params") or {})
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        self._running = False
