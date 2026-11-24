# PROGRESS

## Stage 0 - research
- Environment verified: Python 3.12.10, Chrome present, Playwright browsers present, git works.
- GeoLeadScraper cloned and studied (field paths for Google/Yandex/2GIS recorded in DECISIONS.md).
- Reference images exist in docs/reference (4 files), will view once at stage 6.

## Stage 1 - foundation + capture tooling
- Skeleton, config, db, models, logging, browser manager, capture/peek tools, run.bat/run.py done.
- tests: db/config/peek/health/blocks/capture -> 28 passed; ruff clean; /health OK via run.py; committed.

## Stage 5 - normalize, dedupe, jobs
- normalize.py/dedupe.py/jobs.py/events.py/geo.py + tools/run_job.py implemented; fake-scraper tests cover dedupe/skip/pause/stop/SourceChanged (55 tests pass).
- Fixed pause_event init (worker hang) and shared BrowserManager per job; live run_job 3 sources: google=20 yandex=20 twogis=12 (52 total).
- ruff clean; committed.
