"""In-process event bus for SSE (SPEC 6)."""

from __future__ import annotations

import json
import logging
import queue
import threading
from collections.abc import Iterator

log = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._subscribers: dict[int, queue.Queue] = {}
        self._lock = threading.Lock()
        self._counter = 0

    def subscribe(self, job_id: int) -> queue.Queue:
        with self._lock:
            q: queue.Queue = queue.Queue(maxsize=500)
            self._subscribers[job_id] = q
            return q

    def unsubscribe(self, job_id: int) -> None:
        with self._lock:
            self._subscribers.pop(job_id, None)

    def publish(self, job_id: int, event: str, data: dict) -> None:
        with self._lock:
            q = self._subscribers.get(job_id)
            self._counter += 1
            seq = self._counter
        if q is None:
            return
        payload = {"seq": seq, "event": event, "data": data}
        try:
            q.put_nowait(payload)
        except queue.Full:
            try:
                q.get_nowait()
                q.put_nowait(payload)
            except queue.Empty:
                pass

    def stream(self, job_id: int, timeout: float = 15.0, max_events: int = 1000) -> Iterator[str]:
        q = self.subscribe(job_id)
        try:
            yield ": connected\n\n"
            emitted = 0
            iterations = 0
            max_iterations = max_events * 10
            while emitted < max_events and iterations < max_iterations:
                iterations += 1
                try:
                    item = q.get(timeout=timeout)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                emitted += 1
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
                if item["event"] in ("done", "error"):
                    break
        finally:
            self.unsubscribe(job_id)


event_bus = EventBus()
