# PROGRESS

## Stage 0 - research
- Environment verified: Python 3.12.10, Chrome present, Playwright browsers present, git works.
- GeoLeadScraper cloned and studied (field paths for Google/Yandex/2GIS recorded in DECISIONS.md).
- Reference images exist in docs/reference (4 files), viewed once at stage 6.

## Stage 1 - foundation + capture tooling
- Skeleton, config, db, models, logging, browser manager, capture/peek tools, run.bat/run.py done.
- tests: db/config/peek/health/blocks/capture -> 28 passed; ruff clean; /health OK via run.py; committed.

## Stage 2 - Google Maps scraper
- Geoleadscraper hints; capture google 'барбершоп' Saratov --auto done; results/detail saved.
- base.py (RawPlace/BaseScraper/errors/dedupe helpers) + google.py (pure parse + browser layer) implemented.
- tests: google parser unit tests; ruff clean; live scrape found=20 rows (coverage fields empty in DOM path).

## Stage 3 - Yandex scraper
- Yandex captures (2) saved; results.html + XHR responses in tests/fixtures/yandex.
- Pure parser + browser layer with anchor selector; live scrape found=20 rows after headed-browser fix.

## Stage 4 - 2GIS scraper
- Captures saved; resp_0002/0004.json + detail.html in tests/fixtures/twogis.
- parse_twogis_payload + browser layer with city slug mapping; live run found=12 rows (known issue).

## Stage 5 - normalize, dedupe, jobs
- normalize/dedupe/jobs/events/geo + run_job CLI; fake-scraper tests cover dedupe/skip/pause/stop/SourceChanged.
- live run_job: google=20 yandex=20 twogis=12 (52 leads); fixed pause_event init + shared BrowserManager.

## Stage 8 - enrichment and flags
- enrich/site.py (httpx, 8s timeout, 2MB, max 3 pages), socials.py, template_detect.py; flags computation wired into job step.
- Manual 'Обогатить выбранные' API + button; dead sites never fail job.
- tests on saved HTML samples: 66 pass; ruff clean.
