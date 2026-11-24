"""Run a full job from the CLI: python -m app.tools.run_job --country 'Россия' --cities 'Саратов,Энгельс' ..."""

from __future__ import annotations

import argparse
import sys

from app.core.jobs import JobRunner
from app.db import session_scope
from app.logging_setup import setup_logging


def run_job(params: dict) -> int:
    setup_logging()
    runner = JobRunner()
    with session_scope() as s:
        from app.core.jobs import estimate

        est = estimate(s, params)
    print(f"[job] estimate: {est}")
    job = runner.create_job(params)
    print(f"[job] created job #{job.id} status={job.status}")
    runner.start(job.id)
    runner.wait(job.id, timeout=float(params.get("max_minutes", 60)) * 60 + 60)
    job = runner.get_job(job.id)
    print(f"[job] finished status={job.status}")
    print(f"[job] counters: {job.counters}")
    with session_scope() as s:
        from app.models import JobPair

        pairs = s.query(JobPair).filter_by(job_id=job.id).all()
        for p in pairs:
            print(f"[job] pair {p.city}/{p.category}/{p.source}: {p.status} found={p.found} error={p.error}")
    return 0 if job.status in ("done", "stopped") else 1


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Run a scraping job end to end")
    ap.add_argument("--country", default="Россия")
    ap.add_argument("--cities", default="Саратов")
    ap.add_argument("--categories", default="барбершоп")
    ap.add_argument("--sources", default="google,yandex,twogis")
    ap.add_argument("--max", type=int, default=60)
    ap.add_argument("--skip-days", type=int, default=14)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    params = {
        "country": args.country,
        "cities": [c.strip() for c in args.cities.split(",") if c.strip()],
        "categories": [c.strip() for c in args.categories.split(",") if c.strip()],
        "sources": [s.strip() for s in args.sources.split(",") if s.strip()],
        "max_results_per_pair": args.max,
        "skip_days": args.skip_days,
        "force": args.force,
    }
    return run_job(params)


if __name__ == "__main__":
    raise SystemExit(main())
