"""Supervisor: restart crashed module workers with exponential backoff (SPEC 9)."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class WorkerState:
    module_id: str
    running: bool = False
    failures: int = 0
    last_failure: float = 0.0
    status: str = "stopped"
    thread: threading.Thread | None = None


class Supervisor:
    MAX_PER_HOUR = 5

    def __init__(self):
        self.workers: dict[str, WorkerState] = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def register(self, module_id: str, worker_fn) -> None:
        self.workers[module_id] = WorkerState(module_id=module_id)
        self.workers[module_id]._worker_fn = worker_fn  # type: ignore[attr-defined]

    def start(self, module_id: str) -> bool:
        state = self.workers.get(module_id)
        if state is None or state.running:
            return False
        state.running = True
        state.status = "running"
        state.thread = threading.Thread(target=self._run_worker, args=(module_id,), daemon=True, name=f"hub-{module_id}")
        state.thread.start()
        return True

    def stop(self, module_id: str) -> None:
        state = self.workers.get(module_id)
        if state:
            state.running = False
            state.status = "stopped"

    def _run_worker(self, module_id: str) -> None:
        state = self.workers[module_id]
        recent: deque[float] = deque(maxlen=self.MAX_PER_HOUR)
        while state.running and not self._stop.is_set():
            try:
                state._worker_fn()  # type: ignore[attr-defined]
                break
            except Exception:  # noqa: BLE001
                now = time.time()
                while recent and now - recent[0] > 3600:
                    recent.popleft()
                recent.append(now)
                state.failures += 1
                state.last_failure = now
                if len(recent) >= self.MAX_PER_HOUR:
                    state.status = "error"
                    state.running = False
                    break
                delay = min(2 ** min(state.failures, 5), 30)
                time.sleep(delay)

    def status(self, module_id: str) -> str:
        state = self.workers.get(module_id)
        return state.status if state else "stopped"

    def shutdown(self) -> None:
        self._stop.set()
        for state in self.workers.values():
            state.running = False
