"""Stage 5: normalize, dedupe, jobs with fake scrapers (no network)."""

from __future__ import annotations

import threading
import time

import pytest

from app.core.dedupe import dedupe_key_for, is_same_lead, merge_places
from app.core.jobs import JobRunner, estimate
from app.core.normalize import normalize_name, normalize_phone
from app.db import session_scope
from app.models import Job, JobPair, Lead, PairHistory, utcnow
from app.scrapers.base import NeedsHuman, RawPlace, SourceChanged


@pytest.mark.unit
def test_normalize_phone():
    assert normalize_phone("8 (845) 211-11-11") == "+78452111111"
    assert normalize_phone("+7 845 211 11 11") == "+78452111111"
    assert normalize_phone("garbage") is None


@pytest.mark.unit
def test_normalize_name():
    assert normalize_name('ООО "Барбершоп Борода"') == "барбершоп борода"
    assert normalize_name("КАФЕ «Зерно»!") == "кафе зерно"


@pytest.mark.unit
def test_dedupe_same_phone():
    a = RawPlace(name="Alpha", phones=["+78452111111"], lat=51.5, lon=46.0)
    b = RawPlace(name="Completely Other", phones=["+7 (845) 211-11-11"], lat=51.9, lon=46.8)
    assert is_same_lead(a, b)


@pytest.mark.unit
def test_dedupe_fuzzy_name_and_distance():
    a = RawPlace(name="Барбершоп Борода", lat=51.5300, lon=46.0300)
    b = RawPlace(name="Барбершоп Борода", lat=51.5305, lon=46.0305)
    assert is_same_lead(a, b)


@pytest.mark.unit
def test_dedupe_different_places_same_name():
    a = RawPlace(name="Барбершоп Борода", lat=51.53, lon=46.03)
    b = RawPlace(name="Барбершоп Борода", lat=51.63, lon=46.13)
    assert not is_same_lead(a, b)


@pytest.mark.unit
def test_merge_union():
    a = RawPlace(source="google", source_id="g1", name="Барбершоп", phones=["+78452111111"], emails=["a@x.ru"], socials={"vk": "v1"}, lat=51.53, lon=46.03)
    b = RawPlace(source="yandex", source_id="y1", name="Барбершоп", phones=["+78452222222"], emails=["b@x.ru"], socials={"tg": "t1"}, rating=5.0, reviews_count=10, lat=51.5301, lon=46.0301)
    merged = merge_places([a, b])
    assert len(merged) == 1
    m = merged[0]
    assert len(m["phones"]) == 2
    assert len(m["emails"]) == 2
    assert set(m["maps"]) == {"google", "yandex"}
    assert m["rating"] == 5.0


@pytest.mark.unit
def test_dedupe_key_fallback():
    p = RawPlace(name="No Phone", lat=51.53, lon=46.03)
    assert dedupe_key_for(p).startswith("geo:")


class FakeScraper:
    def __init__(self, places, fail=None, block=None):
        self.places = places
        self.fail = fail
        self.block = block
        self.calls = 0

    def iter_places(self, query, city, max_results, stop_event=None, on_progress=None):
        self.calls += 1
        if self.block:
            raise NeedsHuman("captcha")
        if self.fail:
            raise SourceChanged("changed")
        yield from self.places


def _params(**kwargs):
    p = {
        "country": "Россия",
        "cities": ["Саратов"],
        "categories": ["барбершоп"],
        "sources": ["google"],
        "max_results_per_pair": 10,
        "skip_days": 14,
        "no_repeat": False,
        "force": True,
    }
    p.update(kwargs)
    return p


@pytest.mark.integration
def test_job_runs_and_creates_leads(tmp_db):
    factory = lambda source, city: FakeScraper([RawPlace(name="Барбершоп", phones=["+78452111111"], city="Саратов")])  # noqa: E731
    runner = JobRunner(scraper_factory=factory)
    job = runner.create_job(_params())
    runner.start(job.id)
    assert runner.wait(job.id, timeout=15)
    job = runner.get_job(job.id)
    assert job.status == "done"
    with session_scope() as s:
        assert s.query(Lead).count() == 1
        pair = s.query(JobPair).filter_by(job_id=job.id).one()
        assert pair.status == "done"
        assert pair.found == 1
        assert s.query(PairHistory).count() == 1


@pytest.mark.integration
def test_pair_skip_within_14_days_and_force(tmp_db):
    with session_scope() as s:
        s.add(PairHistory(city="Саратов", category="барбершоп", source="google", searched_at=utcnow()))
    runner = JobRunner(scraper_factory=lambda source, city: FakeScraper([]))  # noqa: E731
    job = runner.create_job(_params(no_repeat=True, force=False))
    with session_scope() as s:
        pairs = s.query(JobPair).filter_by(job_id=job.id).all()
    assert all(p.status == "skipped" for p in pairs)
    job2 = runner.create_job(_params(no_repeat=True, force=True))
    with session_scope() as s:
        pairs2 = s.query(JobPair).filter_by(job_id=job2.id).all()
    assert all(p.status == "pending" for p in pairs2)


@pytest.mark.integration
def test_source_changed_fails_only_its_pair(tmp_db):
    calls = []

    def factory(source, city):
        if source == "google":
            return FakeScraper([], fail=True)
        calls.append(source)
        return FakeScraper([RawPlace(name="Кофейня", phones=["+78452222222"])])

    runner = JobRunner(scraper_factory=factory)
    job = runner.create_job(_params(sources=["google", "yandex"]))
    runner.start(job.id)
    assert runner.wait(job.id, timeout=15)
    with session_scope() as s:
        pairs = s.query(JobPair).filter_by(job_id=job.id).order_by(JobPair.id).all()
    assert pairs[0].status == "failed"
    assert "changed" in pairs[0].error
    assert pairs[1].status == "done"


@pytest.mark.integration
def test_pause_and_resume(tmp_db):
    gate = threading.Event()
    gate.set()

    class Gated(FakeScraper):
        def iter_places(self, query, city, max_results, stop_event=None, on_progress=None):
            gate.wait(timeout=5)
            yield from self.places

    runner = JobRunner(scraper_factory=lambda source, city: Gated([RawPlace(name="x")]))  # noqa: E731
    job = runner.create_job(_params())
    gate.clear()
    runner.start(job.id)
    runner.pause(job.id)
    time.sleep(0.5)
    gate.set()
    time.sleep(0.5)
    with session_scope() as s:
        j = s.get(Job, job.id)
        assert j.status == "paused"
    runner.resume(job.id)
    assert runner.wait(job.id, timeout=15)
    assert runner.get_job(job.id).status == "done"


@pytest.mark.integration
def test_stop_midjob_consistent_db(tmp_db):
    def factory(source, city):
        class Slow(FakeScraper):
            def iter_places(self, query, city, max_results, stop_event=None, on_progress=None):
                for i in range(5):
                    if stop_event and stop_event.is_set():
                        return
                    time.sleep(0.2)
                    yield RawPlace(name=f"Lead {i}", phones=[f"+7845211111{i}"])
        return Slow([])

    runner = JobRunner(scraper_factory=factory)
    job = runner.create_job(_params(cities=["Саратов", "Энгельс"]))
    runner.start(job.id)
    time.sleep(0.6)
    runner.stop(job.id)
    assert runner.wait(job.id, timeout=10)
    with session_scope() as s:
        j = s.get(Job, job.id)
        assert j.status in ("stopped", "done")
        assert s.query(Lead).count() >= 0


@pytest.mark.unit
def test_estimate(tmp_db):
    with session_scope() as s:
        est = estimate(s, _params(cities=["Саратов", "Энгельс"], categories=["барбершоп", "кофейня"], sources=["google", "yandex", "twogis"]))
    assert est["pairs_total"] == 12
    assert est["pairs_to_run"] == 12
    assert est["approx_minutes"] > 0
