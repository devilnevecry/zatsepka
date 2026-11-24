# PROGRESS

## Stage 0 - research
- Environment verified: Python 3.12.10, Chrome present, Playwright browsers present, git works.
- GeoLeadScraper cloned and studied (field paths for Google/Yandex/2GIS recorded in DECISIONS.md).
- Reference images exist in docs/reference (4 files), will view once at stage 6.

## Stage 1 - foundation + capture tooling
- Skeleton, config, db, models, logging, browser manager, capture/peek tools, run.bat/run.py done.
- tests: db/config/peek/health/blocks/capture -> 28 passed; ruff clean; /health OK via run.py; committed.

## Stage 4 - 2GIS scraper
- Captures saved; resp_0002/0004.json + detail.html in tests/fixtures/twogis.
- parse_twogis_payload + parse_twogis_page_state + browser layer with city slug mapping; live run found=12 rows (recorded as known issue).
- tests: 42 pass; ruff clean.
