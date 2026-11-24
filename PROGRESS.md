# PROGRESS

## Stage 0 - research
- Environment verified: Python 3.12.10, Chrome present, Playwright browsers present, git works.
- GeoLeadScraper cloned and studied (field paths for Google/Yandex/2GIS recorded in DECISIONS.md).
- Reference images exist in docs/reference (4 files), will view once at stage 6.

## Stage 1 - foundation + capture tooling
- Skeleton, config, db, models, logging, browser manager, capture/peek tools, run.bat/run.py done.
- tests: db/config/peek/health/blocks/capture -> 28 passed; ruff clean; /health OK via run.py; committed.

## Stage 3 - Yandex scraper
- Yandex captures (2) saved; results.html + XHR responses copied to tests/fixtures/yandex.
- Pure parser parse_yandex_state + browser layer with anchor selector; live scrape found=20 rows after headed-browser fix.
- tests: 38 total pass; ruff clean; DECISIONS findings recorded.
