# FINAL REPORT - РАЗВЕДКА

## What works
Local FastAPI app (127.0.0.1:8000) started by `run.bat`: search across Google Maps, Yandex Maps and 2GIS; dedupe/merge; site enrichment and flags; lead cards with Base/messages tabs; drawer with prompts, channel links and message statuses; charts, hub dashboard, queue, supervisor, diagnostics. No cloud LLM calls, no accounts, no paid APIs, no CDN at runtime. Ollama is a status indicator only. Nothing is ever sent automatically.

## Tests and coverage
- `pytest -q`: 93 passed, 4 live deselected, ~22 s offline.
- Coverage: 80.5% overall (target 75%); core modules ~90% (target 85%); pure scraper parsers tested on fixtures and synthetic captured payloads.
- UI smoke: every page loads with 0 console errors / failed requests; screenshot of each page at 1440x900 in `debug/ui/`; theme toggle, tabs, drawer, hotkeys verified.
- E2E: fake scrapers -> run job from UI -> live cards -> add to base -> build prompt -> paste -> generate link -> mark sent.
- ruff: clean. `pytest -m live -q`: 4 passed (8m42s).

## Live results (Country Россия, city Саратов, query 'барбершоп', max 20 each)
| Source | Rows | Name | Phone | Website | Rating | Geo |
|---|---|---|---|---|---|---|
| Google | 20 | 20 (100%) | 0 | 0 | 0 | 0 |
| Yandex | 20 | 20 (100%) | 0 | 0 | 0 | 0 |
| 2GIS | 12 | 12 (100%) | 0 | 0 | 0 | 0 |
Full live cycle: 3 sources, 52 leads collected, merged into local DB; prompt built; link generated; status `waiting_reply` after mark-sent; no requests to messenger domains (only generated URLs). Raw log: `debug/live_tests.log`.

## KNOWN ISSUES
1. Live DOM path of the three scrapers returns name (and address text) but no phone/website/rating/coordinates; pure JSON parsers that extract every field are implemented and tested on captured fixtures, but the live pages' JSON endpoints were not reliably reachable during capture. Evidence: `debug/live_tests.log` field-coverage table above. Impact: enrichment and flag detection have no data to work with on live runs. Workaround: full field extraction is available via the pure parsers when JSON payloads are captured; manual lead editing in the drawer.
2. 2GIS live search for 'барбершоп' in Саратов exposes 12 firms, below the 15-row stage target; two live attempts with different scroll strategies produced identical results. Evidence: `debug/capture/twogis/*`, `debug/live_tests.log`.
3. Live full cycle generates `https://t.me/` fallback when a lead has no phone/social captured (text is still copied to clipboard); no target username is invented. Evidence: `debug/live_tests.log` full-cycle line.

## Needs live verification
None: all three sources were reached live from Saratov with a real headed browser.

## How to run
Double-click `run.bat` (creates `.venv`, installs requirements, installs Chromium, starts Uvicorn and opens the browser). Tests: `.venv\Scripts\python.exe -m pytest -q`; coverage: add `--cov=app --cov-report=term`; live: `-m live`. Data: `data/`, debug: `debug/`, logs: `logs/`. See `README.md` and `SPEC_CHECKLIST.md`.

## SPEC acceptance checklist
See `SPEC_CHECKLIST.md` (all sections 1-9 PASS except section 3 "every exposed lead field captured live" PARTIAL - see KNOWN ISSUE 1).
