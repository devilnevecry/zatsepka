"""Job runner: single worker thread, pair queue, checkpoints, pause/resume/stop (SPEC 6)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.dedupe import upsert_lead
from app.core.events import event_bus
from app.db import session_scope
from app.models import Job, JobPair, PairHistory, utcnow
from app.scrapers.base import NeedsHuman, RawPlace, SourceChanged, Stopped

SOURCES = ("google", "yandex", "twogis")


@dataclass
class JobHandle:
    job_id: int
    stop_event: threading.Event = field(default_factory=threading.Event)
    pause_event: threading.Event = field(default_factory=threading.Event)
    human_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    error: str = ""


class JobRunner:
    def __init__(self, scraper_factory=None):
        self.scraper_factory = scraper_factory
        self._handles: dict[int, JobHandle] = {}
        self._lock = threading.Lock()

    def create_job(self, params: dict[str, Any]) -> Job:
        with session_scope() as session:
            job = Job(params=dict(params), status="queued", counters={"found": 0, "unique": 0, "sources": {}})
            session.add(job)
            session.flush()
            cities = params.get("cities") or ["Саратов"]
            categories = params.get("categories") or ["барбершоп"]
            sources = params.get("sources") or list(SOURCES)
            skip_days = int(params.get("skip_days", 14))
            no_repeat = params.get("no_repeat", True)
            force = params.get("force", False)
            cutoff = utcnow() - timedelta(days=skip_days)
            for city in cities:
                for category in categories:
                    for source in sources:
                        status = "pending"
                        if no_repeat and not force:
                            recent = (
                                session.query(PairHistory)
                                .filter(
                                    PairHistory.city == city,
                                    PairHistory.category == category,
                                    PairHistory.source == source,
                                    PairHistory.searched_at >= cutoff,
                                )
                                .first()
                            )
                            if recent:
                                status = "skipped"
                        session.add(JobPair(job_id=job.id, city=city, category=category, source=source, status=status))
            session.flush()
            job_id = job.id
        return self.get_job(job_id)

    def get_job(self, job_id: int) -> Job:
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise KeyError(job_id)
            session.expunge(job)
            return job

    def start(self, job_id: int) -> JobHandle:
        with self._lock:
            handle = self._handles.get(job_id)
            if handle and handle.thread and handle.thread.is_alive():
                return handle
            handle = JobHandle(job_id=job_id)
            handle.pause_event.set()
            handle.human_event.set()
            self._handles[job_id] = handle
        handle.thread = threading.Thread(target=self._run, args=(job_id, handle), daemon=True, name=f"job-{job_id}")
        handle.thread.start()
        return handle

    def pause(self, job_id: int) -> None:
        handle = self._handles.get(job_id)
        if handle:
            handle.pause_event.clear()
        with session_scope() as s:
            job = s.get(Job, job_id)
            if job and job.status in ("running", "queued"):
                job.status = "paused"

    def resume(self, job_id: int) -> None:
        handle = self._handles.get(job_id)
        if handle:
            handle.pause_event.set()
            handle.human_event.set()
        with session_scope() as s:
            job = s.get(Job, job_id)
            if job and job.status in ("paused", "needs_human"):
                job.status = "running"

    def stop(self, job_id: int) -> None:
        handle = self._handles.get(job_id)
        if handle:
            handle.stop_event.set()
            handle.pause_event.set()
            handle.human_event.set()
        with session_scope() as s:
            job = s.get(Job, job_id)
            if job and job.status in ("running", "queued", "paused", "needs_human"):
                job.status = "stopped"

    def clear_human(self, job_id: int) -> None:
        handle = self._handles.get(job_id)
        if handle:
            handle.human_event.set()

    def wait(self, job_id: int, timeout: float = 60.0) -> bool:
        handle = self._handles.get(job_id)
        if handle is None or handle.thread is None:
            return True
        handle.thread.join(timeout=timeout)
        return not handle.thread.is_alive()

    def _wait_while_paused(self, handle: JobHandle) -> None:
        while not handle.pause_event.is_set() and not handle.stop_event.is_set():
            time.sleep(0.2)

    def _run(self, job_id: int, handle: JobHandle) -> None:
        started = utcnow()
        manager = None
        if self.scraper_factory is None:
            from app.browser.manager import BrowserManager

            try:
                manager = BrowserManager(headless=False)
                manager.start()
            except Exception as exc:  # noqa: BLE001
                event_bus.publish(job_id, "error", {"error": str(exc)})
                manager = None
        with session_scope() as s:
            job = s.get(Job, job_id)
            if job:
                job.status = "running"
                job.started_at = started
        event_bus.publish(job_id, "progress", {"status": "running"})
        try:
            while True:
                with session_scope() as s:
                    job = s.get(Job, job_id)
                    if job is None or handle.stop_event.is_set() or job.status in ("stopped", "failed"):
                        break
                    pair = (
                        s.query(JobPair)
                        .filter(JobPair.job_id == job_id, JobPair.status == "pending")
                        .order_by(JobPair.id)
                        .first()
                    )
                    if pair is None:
                        job.status = "done"
                        job.finished_at = utcnow()
                        break
                    pair.status = "running"
                    pair.started_at = utcnow()
                    pair_id = pair.id
                    city, category, source = pair.city, pair.category, pair.source
                    params = dict(job.params or {})
                self._wait_while_paused(handle)
                if handle.stop_event.is_set():
                    with session_scope() as s:
                        p = s.get(JobPair, pair_id)
                        if p:
                            p.status = "pending"
                    break
                try:
                    found = self._run_pair(job_id, pair_id, source, query=category, city=city, params=params, handle=handle, manager=manager)
                except NeedsHuman as exc:
                    with session_scope() as s:
                        pair_row = s.get(JobPair, pair_id)
                        if pair_row:
                            pair_row.status = "pending"
                        j = s.get(Job, job_id)
                        if j:
                            j.status = "needs_human"
                    event_bus.publish(job_id, "needs_human", {"source": source, "reason": exc.reason})
                    handle.human_event.clear()
                    while not handle.human_event.is_set() and not handle.stop_event.is_set():
                        time.sleep(1.0)
                    with session_scope() as s:
                        j = s.get(Job, job_id)
                        if j and j.status == "needs_human":
                            j.status = "running"
                    continue
                except SourceChanged as exc:
                    with session_scope() as s:
                        p = s.get(JobPair, pair_id)
                        if p:
                            p.status = "failed"
                            p.error = str(exc)[:500]
                            p.finished_at = utcnow()
                    event_bus.publish(job_id, "error", {"source": source, "error": str(exc)})
                    continue
                except Stopped:
                    with session_scope() as s:
                        p = s.get(JobPair, pair_id)
                        if p:
                            p.status = "pending"
                    break
                except Exception as exc:  # noqa: BLE001 - one bad pair must not kill the job
                    with session_scope() as s:
                        p = s.get(JobPair, pair_id)
                        if p:
                            p.status = "failed"
                            p.error = str(exc)[:500]
                            p.finished_at = utcnow()
                    event_bus.publish(job_id, "error", {"source": source, "error": str(exc)})
                    continue
                with session_scope() as s:
                    p = s.get(JobPair, pair_id)
                    if p:
                        p.status = "done"
                        p.found = found
                        p.finished_at = utcnow()
                    s.add(PairHistory(city=city, category=category, source=source, searched_at=utcnow()))
                    j = s.get(Job, job_id)
                    if j:
                        counters = dict(j.counters or {})
                        counters["found"] = counters.get("found", 0) + found
                        sources_count = dict(counters.get("sources", {}))
                        sources_count[source] = sources_count.get(source, 0) + found
                        counters["sources"] = sources_count
                        j.counters = counters
                        self._checkpoint(job_id, counters)
        finally:
            if manager is not None:
                try:
                    manager.close()
                except Exception:  # noqa: BLE001
                    pass
            with session_scope() as s:
                j = s.get(Job, job_id)
                if j and j.status == "running":
                    j.status = "done"
                    j.finished_at = utcnow()
        event_bus.publish(job_id, "done", {"job_id": job_id})

    def _checkpoint(self, job_id: int, counters: dict) -> None:
        with session_scope() as s:
            j = s.get(Job, job_id)
            if j:
                j.counters = counters

    def _run_pair(self, job_id: int, pair_id: int, source: str, query: str, city: str, params: dict, handle: JobHandle, manager=None) -> int:
        if self.scraper_factory is not None:
            scraper = self.scraper_factory(source, city)
        else:
            from app.core.geo import scraper_for

            scraper = scraper_for(source, manager=manager, settings=params)
            if manager is None:
                raise RuntimeError("BrowserManager is not started")
        if hasattr(scraper, "stop_event"):
            scraper.stop_event = handle.stop_event
        max_results = int(params.get("max_results_per_pair", 60))
        max_minutes = int(params.get("max_minutes", 60))
        deadline = time.monotonic() + max_minutes * 60
        count = 0
        phone_region = params.get("phone_region", "RU")
        places: list[RawPlace] = []
        for place in scraper.iter_places(query, city, max_results, stop_event=handle.stop_event):
            if handle.stop_event.is_set() or time.monotonic() > deadline:
                raise Stopped()
            places.append(place)
            count += 1
            if count % 10 == 0:
                event_bus.publish(job_id, "progress", {"pair_id": pair_id, "found": count, "source": source})
        unique = 0
        new_lead_ids: list[int] = []
        with session_scope() as session:
            from app.core.dedupe import merge_places

            merged = merge_places(places, phone_region)
            for data in merged:
                place = RawPlace(
                    source=source,
                    name=data.get("name", ""),
                    phones=data.get("phones", []),
                    website=data.get("website", ""),
                    socials=data.get("socials", {}),
                    emails=data.get("emails", []),
                    lat=data.get("lat"),
                    lon=data.get("lon"),
                    category=data.get("category", ""),
                    address=data.get("address", ""),
                    rating=data.get("rating"),
                    reviews_count=data.get("reviews_count"),
                    hours=data.get("hours") or {},
                    attributes=data.get("attributes") or [],
                    extra=data.get("extra") or {},
                )
                lead = upsert_lead(session, data, job_id=job_id)
                unique += 1
                new_lead_ids.append(lead.id)
        for lead_id in new_lead_ids:
            event_bus.publish(job_id, "lead", {"id": lead_id, "source": source})
        return unique


def estimate(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    cities = params.get("cities") or ["Саратов"]
    categories = params.get("categories") or ["барбершоп"]
    sources = params.get("sources") or list(SOURCES)
    pairs_total = len(cities) * len(categories) * len(sources)
    skip_days = int(params.get("skip_days", 14))
    cutoff = utcnow() - timedelta(days=skip_days)
    skipped = 0
    if params.get("no_repeat", True) and not params.get("force", False):
        for city in cities:
            for category in categories:
                for source in sources:
                    if (
                        session.query(PairHistory)
                        .filter(
                            PairHistory.city == city,
                            PairHistory.category == category,
                            PairHistory.source == source,
                            PairHistory.searched_at >= cutoff,
                        )
                        .first()
                    ):
                        skipped += 1
    to_run = pairs_total - skipped
    approx_minutes = round(to_run * 2.5, 1)
    return {
        "pairs_total": pairs_total,
        "pairs_skipped": skipped,
        "pairs_to_run": to_run,
        "approx_minutes": approx_minutes,
    }
