# SPEC checklist (stage 12 pass/fail)

| Section | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Layout: app/, tests/, data/, debug/, logs/ | PASS | repository tree |
| 2 | Data model Lead/Job/JobPair/PairHistory/Message/Template/Setting | PASS | app/models.py; tests/test_db.py |
| 3 | RawPlace, BaseScraper.iter_places, pure parsers, errors, caps | PASS | app/scrapers/base.py + 3 sources; parser unit tests |
| 3 | Every exposed lead field captured | PARTIAL | JSON paths parsed; DOM fallback captures name/address only - see KNOWN_ISSUES |
| 4 | Sync Playwright in worker thread, persistent context, response capture, block detection | PASS | app/browser/manager.py; blocks.py |
| 5 | Phones E.164, name normalization, dedupe, merge | PASS | tests/test_jobs.py dedupe cases |
| 6 | Single worker, checkpoints, pause/resume/stop, PairHistory skip, SSE, estimates | PASS | app/core/jobs.py; tests/test_jobs.py |
| 6 | No money/budget UI | PASS | no such UI |
| 7 | Dark glass theme, rail, Search page, cards, drawer, Base | PASS | app/web/templates + CSS + JS; debug/ui/*.png |
| 8 | Prompts, channel links, messages, templates, batch export | PASS | app/ai/prompts.py, routes/outreach.py; tests/test_outreach.py |
| 9 | Hub registry/dashboard/logs/queue/supervisor/metrics | PASS | app/hub/*; tests/test_hub.py |
| 9 | Ollama status only, no cloud LLM calls | PASS | app/ai/ollama.py (GET /api/ps only) |
| Hard | 127.0.0.1 only, no reload, vendored libs, no CDN | PASS | run.py, run.bat, static/vendor |
| Hard | UTF-8 console in tools | PASS | sys.stdout.reconfigure in all CLI entry points |
| Test | pytest -q offline <3 min, coverage | PASS | 93 tests, ~24s, 80.4% coverage |
| Test | UI smoke: 0 console errors, key elements, theme, drawer | PASS | tests/test_ui.py; debug/ui/ screenshots |
| Test | E2E fake scrapers: job -> cards -> base -> prompt -> link -> sent | PASS | tests/test_ui.py + tests/test_outreach.py |
| Test | Live full cycle Saratov / барбершоп / 3 sources | PASS | tests/test_live.py; debug/live_tests.log |
| Stage 12 | run.bat clean clone end-to-end, DB backup, log rotation, diagnostics | PASS | run.bat, db_backup.py, logging_setup.py, /page/diagnostics |
