# PROGRESS

## Stage 0 - research
- Environment verified: Python 3.12.10, Chrome present, Playwright browsers present, git works.
- GeoLeadScraper cloned and studied (field paths for Google/Yandex/2GIS recorded in DECISIONS.md).
- Reference images exist in docs/reference (4 files), will view once at stage 6.

## Stage 1 - foundation + capture tooling
- Skeleton, config, db, models, logging, browser manager, capture/peek tools, run.bat/run.py done.
- tests: db/config/peek/health/blocks/capture -> 28 passed; ruff clean; /health OK via run.py; committed.

## Stage 2 - Google Maps scraper
- Geoleadscraper hints; capture google 'барбершоп' Saratov --auto done; results/detail saved.
- base.py (RawPlace/BaseScraper/errors/dedupe helpers) + google.py (pure parse + browser layer) implemented.
- tests: google parser unit tests (34 total pass); ruff clean; live scrape found=20 rows (coverage fields empty in DOM path).
