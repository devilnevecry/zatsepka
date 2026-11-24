# PROJECT.md - Zatsepka clone, build the whole project autonomously

You are the only engineer. Deliver a finished, tested, runnable local app that works like the reference screen recordings (docs/reference/ has frames; SPEC section 7 is the visual contract). Work through stages 1-12 in order, continuously, then final acceptance. This file is complete: nothing else is needed from the user.

## Autonomy rules
- Never stop between stages. No stage reports in chat. Do not ask the user questions and do not ask for more prompt text: resolve ambiguity with the defaults in this file and log one line in DECISIONS.md.
- Progress goes to PROGRESS.md (5 lines max per stage). The only message to the user is the final report (15 lines max) after FINAL_REPORT.md exists and acceptance passes.
- Human-only blocker (captcha or consent page in the visible browser): the capture/scrape tools wait up to 10 minutes polling every 5 s. Do not idle: continue offline work meanwhile. If still blocked, mark that source 'needs live verification' in FINAL_REPORT.md and move on.
- If you lose context, re-read these rules and PROGRESS.md, continue from the first unfinished stage, and do not recap.

## Hard constraints
- Free only: no paid APIs, no subscriptions, no API keys for maps, no logins or accounts on any map, no cloud LLM calls from the app. Ollama is only a status indicator on the dashboard. No Docker, no Node build step, no CDN (vendor JS/CSS/fonts into app/web/static).
- Stack is fixed: FastAPI + Uvicorn, Jinja2, HTMX, Alpine.js, SQLAlchemy 2 (sync) + SQLite WAL, Playwright SYNC API inside a worker thread, pydantic v2, httpx, phonenumbers, rapidfuzz, selectolax, openpyxl, psutil, pytest, pytest-cov, ruff. Any other dependency: one line in DECISIONS.md first, only if unavoidable.
- Server binds to 127.0.0.1 only. Code, identifiers, comments in English; UI strings in Russian. Windows 10/11, Python 3.12, pathlib, no bash-only commands in project scripts, no uvicorn --reload.
- Console output is UTF-8: sys.stdout.reconfigure(encoding='utf-8', errors='replace') at the start of every tool. Never degrade output to ASCII.
- All live tests, fixtures and examples use Saratov, Russia (second city Engels). Phone region RU. No other regions in tests or docs.
- Only one browser profile instance at a time: never run two captures or scrapers concurrently.

## Token and loop discipline
1. Do not scan the whole repo; targeted ls/grep, read only the SPEC sections the current stage names.
2. Do exactly the current stage. No extra features or refactors.
3. Fixtures first: never develop a parser against live sites by trial and error. Capture once with `python -m app.tools.capture ... --auto`, then work offline against tests/fixtures. At most 2 live runs per stage for verification.
4. Never print large payloads (HTML, JSON, logs). Save to debug/, inspect with `python -m app.tools.peek <file> [--path a.b.c] [--grep text]`. Console output under ~40 lines.
5. Targeted patches, no whole-file rewrites for small changes, do not re-read a file you just wrote.
6. While working run the narrowest check; full `pytest -q -x` and ruff at the end of a stage.
7. Failure ladder: the same error or failing test gets at most 3 attempts, each with a DIFFERENT hypothesis; never rerun an unchanged command. After 3: (a) use the documented Plan B if one exists, (b) otherwise the smallest workaround that keeps the user-visible behavior, (c) otherwise record the item in KNOWN_ISSUES (FINAL_REPORT.md) with evidence and CONTINUE with the next work item. Revisit each known issue once, at the end. Never stop and never wait for the user.
8. Every loop in app code has hard caps (iterations, stagnation counter, timeouts). No `while True` without a guaranteed exit.
9. Stage end: Definition of Done and tests pass -> PROGRESS.md -> `git add -A && git commit -m 'stage N: ...'` -> start the next stage immediately.
10. Polish budget: at most 2 UI polish passes in total against docs/reference; after that, move on.

## Testing standard (part of every stage's Definition of Done)
- Markers: unit (default), integration, e2e (Playwright against fake scrapers), live (real sites; skipped unless `pytest -m live`).
- `pytest -q` (everything except live) passes offline in under 3 minutes. Coverage via pytest-cov: scraper parse functions >= 90%, core/ >= 85%, overall >= 75%.
- Tests ship in the same stage as the code. Never weaken or delete a test to make it pass; fix the code.
- UI smoke tests: every rail page loads with 0 console errors and 0 failed requests, key elements present, hotkeys work, theme toggle persists, drawer opens and closes.
- E2E: app on a free port with fake scrapers; run a job from the UI, see cards appear, add to base, build a prompt, paste text, assert generated channel URLs (no real navigation), mark sent.
- Live full cycle (stage 12): country Россия, city Саратов, query 'барбершоп', all three sources, max 20 each: collect -> dedupe -> enrich -> pick a lead -> build prompt -> paste text -> generate links. Nothing is ever sent; assert no outbound requests to messenger domains.

# SPEC


## 1. Layout
zatsepka/
  run.py  run.bat  requirements.txt  pyproject.toml
  PROJECT.md  PROGRESS.md  DECISIONS.md  FINAL_REPORT.md
  app/
    main.py  config.py  db.py  models.py  schemas.py  logging_setup.py
    browser/  manager.py  blocks.py
    scrapers/ base.py  google.py  yandex.py  twogis.py
    core/     normalize.py  dedupe.py  jobs.py  events.py
    enrich/   site.py  socials.py  template_detect.py
    ai/       ollama.py  prompts.py
    web/      routes/  templates/  static/ (css, vendored htmx, alpine, chartjs, leaflet)
    hub/      registry.py  supervisor.py  queue.py  metrics.py
    tools/    capture.py  peek.py  scrape.py  run_job.py
  tests/  fixtures/{google,yandex,twogis}/
  data/ (zatsepka.db, browser_profile/)   debug/   logs/   (all gitignored)

## 2. Data model (SQLAlchemy)
- Lead: id, dedupe_key (unique), name, category, address, city, lat, lon, phones (JSON list, E.164), emails (JSON list), website, socials (JSON: instagram, telegram, whatsapp, viber, vk, facebook, youtube), rating, reviews_count, description, hours (JSON), attributes (JSON list), price_range, plus_code, photos_count, top_reviews (JSON list, up to 5), extra (JSON: every other field a source exposes), maps (JSON: {google|yandex|twogis: {id, url}}), flags (JSON: no_site, only_socials, template_site, template_name, chain_count), status (new, in_base, contacted, waiting_reply, replied, deal, rejected), notes, first_seen, updated_at, job_id.
- Job: id, params (JSON), status (queued, running, paused, needs_human, done, failed, stopped), counters (JSON), created_at, started_at, finished_at.
- JobPair: job_id, city, category, source, status (pending, running, done, failed, skipped), found, error, started_at, finished_at.
- PairHistory: city, category, source, searched_at (drives the skip-for-N-days rule).
- Message: id, lead_id, channel (whatsapp, telegram, instagram, viber, call), direction (out, in), text, status (draft, sent), created_at.
- Template: id, name, channel, body, for_flag. Setting: key, value (JSON).
- Tabs: 'Парсер' = leads of the latest job with status new; 'База' = status != new; 'Сообщения' = leads that have messages.

## 3. Scraper contract
- RawPlace (pydantic): source (google|yandex|twogis), source_id, url, name, category, address, lat, lon, phones[], emails[], website, socials{}, rating, reviews_count, description, hours, attributes[], price_range, plus_code, photos_count, top_reviews[], extra{}. Parsers must capture EVERY lead field present in the fixtures (write the field inventory per source into DECISIONS.md, 15 lines max); unknown fields go to extra.
- BaseScraper.iter_places(query, city, max_results, stop_event, on_progress) -> Iterator[RawPlace].
- Parsing is PURE functions (payload or HTML in, list[RawPlace] out) kept apart from browser I/O. Tests run only against pure functions + tests/fixtures.
- Extraction priority: (1) JSON responses the page itself fetches, (2) embedded page state, (3) DOM. Use role/aria/data attributes and stable URLs, never hashed CSS class names. The chosen path per source goes to DECISIONS.md in 10 lines max.
- Errors: NeedsHuman(reason) for captcha, consent, login; SourceChanged(details) when a non-empty page yields 0 places (save debug snapshot, fail the pair, continue the job); Stopped.
- Caps: max_scrolls 60; stop after 3 scrolls with no new items or at the end-of-list marker; per-pair timeout 180 s; detail-card visits only when list data lacks phone or website, and never more than max_results; pause 0.8-2.5 s between actions, 4-10 s between pairs.

## 4. Browser rules
- Sync Playwright in a dedicated worker thread, never inside the asyncio loop.
- launch_persistent_context(data/browser_profile, channel='chrome' with fallback to bundled chromium, headless=False, locale='ru-RU', viewport 1366x850). One context per job, reused across sources.
- Capture JSON through page.on('response') into a bounded deque (200 items, body up to 2 MB).
- No stealth plugins or fingerprint spoofing. Strategy: real Chrome + persistent profile + human pacing + low volume.
- Block detection per source (URL, title, page text markers) -> raise NeedsHuman. UI shows banner 'Нужно ваше участие в окне браузера', backend polls every 3 s until cleared, after 10 min the job goes to paused.

## 5. Normalize and dedupe
- Phones to E.164 via phonenumbers, default region from setting phone_region (default RU). Names: casefold, strip quotes, legal forms and punctuation.
- Same lead if: same phone, OR name token_set_ratio >= 90 (rapidfuzz) AND distance <= 150 m. dedupe_key = first phone, else sha1(name_norm|round(lat,3)|round(lon,3)).
- Merge: union of phones, emails, socials; prefer non-empty fields; keep per-source ids in maps; rating from the source with most reviews.

## 6. Jobs and settings defaults
- Single worker thread, queue of (city, category, source) pairs, checkpoint after every pair and every 10 places; pause/resume/stop through threading.Event; after a crash a job resumes from pending pairs.
- Geo is global: ONE country + city list applies to all three sources; each scraper maps it to its own URL form (Google: '<query> <city>', Yandex: text + city, 2GIS: city slug resolved through its own city search). Defaults: country Россия, city Саратов.
- Skip a pair if PairHistory is younger than skip_days (default 14) unless force.
- Estimate endpoint: pairs total / skipped / to run / approx minutes. Progress via SSE /api/jobs/{id}/events (progress, lead, needs_human, done, error).
- Per-run limits: max_results_per_pair 60, max_minutes 60. There is no money or budget UI anywhere.
- Settings: sources on/off, base domains per source (2gis.ru by default, configurable), pauses, limits, skip_days, phone_region, Ollama URL (dashboard status only), Chrome path, my_offer (text), prompt tone and length.

## 7. UI (visual targets, approximate; images in docs/reference/ if present, view each at most once)
- Dark glass theme by default, light theme via toggle at the rail bottom (labels 'Ночь'/'День'). CSS variables: --bg #0b0c10, --surface rgba(255,255,255,.04), --border rgba(255,255,255,.09), --text #e8e9ee, --muted #8b8fa3. Radius 14-18 px, hairline borders, soft blur, dense layout, 12-14 px type, system font stack.
- Top bar: pin icon + 'ЗАЦЕПКА' + small version text.
- Left rail (~72 px): icon over a tiny label: Профиль (avatar), Поиск, Чаты, Отбор, Сообщения, ИИ, База, Клавиши, Графики, Настройки, Помощь. Active item = lighter rounded tile.
- Поиск page, two columns. Left panel (~380 px, scrolls): city chips (+ add, x remove); category chips with 'добавить все'; block 'Параметры': checkbox 'Не повторять пары «город × категория» за N дней', collapsible 'Тонкая настройка: пауза и лимиты', summary box (N городов × M категорий = K пар, уже искали - пропустим X, осталось Y, примерно Z мин), limit fields, source toggles (Google, Яндекс, 2ГИС), buttons 'Начать поиск' (primary), 'Пауза', 'Стоп' (red outline). Right: pill tabs 'Парсер N' / 'База N' / 'Сообщения N', global search input, dropdown filters (город, тип, сфера, статус), line 'Показано X из Y лидов (в базе Z)', toolbar (export, delete selected), responsive card grid (3-5 columns).
- Lead card: checkbox top-left; flag pill: 'Без сайта' orange, 'Только соцсети' purple, 'Шаблон' yellow, 'Ждёт ответа' yellow outline, 'N компаний' blue; rating chip with star top-right; bold name (2-line clamp); pin + 'город · категория'; row of rounded-square icon buttons Instagram (pink), Telegram (blue), Viber (purple), WhatsApp (green), dimmed when absent; '+ В базу' button; faint dot-grid map thumbnail drawn from lat/lon as inline SVG. Hover: lift + border glow. Click opens the drawer.
- Drawer (right, ~460 px): name; channel row (WhatsApp, Telegram, Instagram, Позвонить); blocks Контакты, Карта (vendored Leaflet + OSM tiles, fallback to dot grid offline), Источники (links to map cards), Заметки, Сообщение (composer); navigation '‹ 7/250 ›' across the current list. 'Профиль' page = local name/avatar + stats (found, in base, contacted, replied); no teams.

## 8. Outreach flow (no LLM calls inside the leads module)
- Per lead the app builds a ready-to-paste PROMPT for a cloud chatbot: lead facts (name, category, city, address, rating, reviews, website and flags, socials, top reviews, hours) + the user's offer text + channel + tone + length + 'output only the final message text, in Russian, no explanations, do not invent facts'. Prompt templates are editable on the 'ИИ' page (variables {name} {category} {city} {address} {rating} {reviews_count} {flag} {website} {socials} {top_reviews} {my_offer} {channel} {tone}). Buttons: 'Собрать промпт' -> 'Скопировать промпт'. Batch: prompts for all selected leads into one downloadable .md file.
- 'Текст сообщения' textarea in the drawer: the user pastes the chatbot answer. Channel buttons then open the target with the text: WhatsApp https://wa.me/<digits>?text=<urlencoded>; Telegram https://t.me/<username> (tg://resolve?phone=... when only a phone) with the text copied to clipboard; Instagram profile URL with the text copied; Viber viber://chat?number=%2B<digits>; Email mailto:<email>?subject=<urlencoded>&body=<urlencoded> (editable subject); call tel:.
- The user always presses send himself. 'Отметить отправленным' (button + hotkey) -> Message(status=sent), lead.status = waiting_reply; 'Ответили' (optional pasted text) -> replied. Auto-send from the user's own account is NOT built.
- Static message templates ({name} {category} {city} {rating} {flag}, default per flag) remain as a fallback for users who skip the chatbot.

## 9. Hub (shell around modules)
- Module interface: id, title, icon, start(params), stop(), status(). Modules: 'leads' (this project) plus placeholders hh, habr, freelance ('скоро').
- Dashboard page ('Дашборд', first item of the rail): a card per module (status stopped/running/queued/error, last run, counters, Start/Stop/'В очередь'); system load via psutil (CPU %, RAM, disk), GPU/VRAM via nvidia-smi when present; Ollama status via GET <ollama_url>/api/ps (loaded model, VRAM) or 'Ollama недоступна' (never an error page).
- Each module logs to logs/<module>.log (rotating); the dashboard has a live log tail per module (SSE, last 200 lines, level filter).
- Queue: modules start individually or through a queue that runs them sequentially; the queue is persisted in the DB and survives restarts.
- 24/7: supervisor restarts a crashed module worker with exponential backoff (max 5 per hour, then status error), graceful shutdown, browser context recycled every 200 pages, all job state persisted.


# STAGES (execute in order, no pauses)

## STAGE 1 - Foundation + capture tooling

Read: SPEC sections 1, 2, 4, 6.
Build:
1. Skeleton from SPEC 1 (only files needed now, including empty app/hub/ package), pinned requirements.txt, pyproject (ruff, pytest), .gitignore, git init.
2. config.py (settings with SPEC 6 defaults, persisted in the settings table), db.py (SQLAlchemy 2 sync, SQLite WAL, create_all + schema_version table), models.py per SPEC 2, rotating log to logs/app.log.
3. run.py: start uvicorn on 127.0.0.1:8000 (no reload), open the default browser tab once /health answers. run.bat: create .venv if missing, install requirements, run `playwright install chromium`, start run.py.
4. browser/manager.py per SPEC 4: context factory, human_pause, response-capture deque, block-detection hook.
5. tools/capture.py: `python -m app.tools.capture <google|yandex|twogis> '<query>' [--city X]` opens the source search in the managed headed browser. Default mode is non-interactive (--auto): wait for the results list (up to 90 s), save the results container HTML, screenshot and all captured JSON responses (url, status, body) to debug/capture/<source>/<timestamp>/, then click the first result and save the detail panel the same way. On a consent/captcha/block page keep polling every 5 s for up to 10 minutes (a human may solve it in the visible window), then exit with a clear code. `--manual` keeps Enter prompts. Ctrl+C safe.
6. tools/peek.py: JSON -> key tree with types and array lengths (depth 4, strings cut to 60 chars); `--path a.b.0.c` prints one node; `--grep text` prints up to 10 matches with paths. HTML -> tag outline of the container showing only aria-label, role, data-* attributes.
Definition of Done: GET /health returns {'ok': true} and run.py opens a tab; models create on a fresh DB; tests for db init and peek on a small sample; ruff clean; capture tool starts and exits cleanly on about:blank (no live maps in this stage).
DONE -> commit, log in PROGRESS.md, go straight to the next stage.

## STAGE 2 - Google Maps scraper

Read: SPEC sections 3, 4, 5.
Steps:
1. Study GeoLeadScraper once (15 minutes of work max): `git clone --depth 1 https://github.com/rohanhake98/GeoLeadScraper docs/ref_geoleadscraper` (fallback https://github.com/ozhehkovski/geoleadscraper; the folder is gitignored). Use grep to find how it locates result cards and extracts fields (names, selectors, data paths). Treat it as a hint for field names and DOM anchors only, never copy code. 8 lines in DECISIONS.md.
1b. Fixtures: if tests/fixtures/google is empty, run `python -m app.tools.capture google 'барбершоп' --city 'Саратов' --auto` and the same for 'кофейня', then copy the useful files into tests/fixtures/google. If a captcha or consent page blocks the run, do not idle: continue with step 3 on what was captured and repeat capture later.
2. Analyse fixtures with peek only; list EVERY lead field the page exposes (hours, description, attributes, price range, photos count, reviews text, plus code, links) and capture all of them, unknown ones into extra. Write findings to DECISIONS.md (10 lines max): where list data lives (XHR, embedded state or DOM), which fields come from the list vs the detail panel, how coordinates and place id are obtained.
3. Implement scrapers/base.py (RawPlace, BaseScraper, errors) and scrapers/google.py: pure parse functions + thin browser layer. Flow: open Google Maps search for '<query> <city>' with hl=ru, handle the consent screen, scroll the results feed under the SPEC 3 caps, open a detail card only when phone or website is missing, yield RawPlace. Block markers (unusual traffic, captcha) -> NeedsHuman.
4. tools/scrape.py: `python -m app.tools.scrape google '<query>' --city '<city>' --max 20` prints a compact table plus coverage stats (percent with phone, website, rating, coordinates).
Known pitfalls: window scrolling does nothing on Google Maps. Scroll the results feed (`[role=feed]`): hover its center, `page.mouse.wheel(0, 3000)`, wait up to 4 s for the article count to grow. If the list still stops short of 15, Plan B: split the query into district sub-queries ('барбершоп <район> Саратов'), merge and dedupe; then the Definition of Done becomes at least 15 unique rows across at least 3 sub-queries.
Definition of Done: parse tests on fixtures extract name + address for at least 90% of captured places; no test touches the network; one live run of tools/scrape returns at least 15 rows and finishes under its caps; ruff clean.
DONE -> commit, log in PROGRESS.md, go straight to the next stage.

## STAGE 3 - Yandex Maps scraper

Read: SPEC sections 3, 4, 5; DECISIONS.md (Google findings, as a pattern only).
Same method as stage 2, in the same order: capture fixtures first (`python -m app.tools.capture yandex 'барбершоп' --city 'Саратов' --auto` twice), peek, DECISIONS.md, pure parsers, thin browser layer, tools/scrape support for `yandex`.
Source specifics to verify in fixtures, not assume: search URL form (yandex.ru/maps/?text=...), the JSON the page fetches for results, virtualized list and how more results load, social links shown on cards, captcha page markers -> NeedsHuman.
Definition of Done: same as stage 2 (90% name+address on fixtures, no network in tests, one live run with at least 15 rows, ruff clean).
DONE -> commit, log in PROGRESS.md, go straight to the next stage.
Also reuse docs/ref_geoleadscraper as a field-name hint if it covers Yandex. Capture EVERY exposed lead field.

## STAGE 4 - 2GIS scraper

Read: SPEC sections 3, 4, 5, 6 (base domain setting).
Same method as stage 2. Capture: `python -m app.tools.capture twogis 'барбершоп' --city 'Саратов' --auto` twice.
Verify in fixtures: how the city is selected in the URL, which JSON the page fetches for the result list (catalog items with contact groups for phones, sites, socials is the likely shape), how pagination or infinite scroll loads more, differences between 2gis.ru and other domains (base domain comes from settings).
Definition of Done: same as stage 2.
DONE -> commit, log in PROGRESS.md, go straight to the next stage.
Also reuse docs/ref_geoleadscraper as a field-name hint if it covers 2GIS. Capture EVERY exposed lead field.

## STAGE 5 - Normalize, dedupe, job runner

Read: SPEC sections 2, 5, 6.
Build: core/normalize.py, core/dedupe.py (merge rules from SPEC 5, writes Lead rows), core/jobs.py (worker thread, pair queue, checkpoints, pause/resume/stop, PairHistory skip rule, NeedsHuman handling, SourceChanged handling, per-run limits, estimate function), core/events.py (in-process event bus for SSE), tools/run_job.py: `python -m app.tools.run_job --country 'Россия' --cities 'Саратов,Энгельс' --categories 'барбершоп,салон красоты' --sources google,yandex,twogis --max 60`.
Definition of Done (tests with fake scrapers, no network): dedupe cases (same phone, fuzzy name + distance, different places with the same name); pair skip within 14 days and force override; pause and resume; stop mid-job leaves a consistent DB; simulated crash resumes from pending pairs; NeedsHuman pauses and continues after clearing; a scraper that raises SourceChanged fails only its pair. One live run_job with 1 city, 1 category, 3 sources, max 20, shows per-source counts and merged unique count. ruff clean.
DONE -> commit, log in PROGRESS.md, go straight to the next stage.
Geo is global per SPEC 6: one country and city list for all sources; add a geo resolver per scraper with tests.

## STAGE 6 - UI shell, Search page, lead cards

Read: SPEC sections 1, 6, 7. View docs/reference/ images once if present.
Build: base layout with top bar and left rail, theme toggle (persisted), vendored htmx/alpine/fonts, CSS variables theme; Поиск page exactly per SPEC 7 (with one country + city selector applying to all sources): chips for cities and categories (stored in settings, with a sensible default category list), estimate box wired to the estimate endpoint, Start/Pause/Stop wired to the job API, SSE live updates that append cards, needs_human banner, tabs with counters, search field, filters, counter line, card grid, '+ В базу' (status in_base). Other rail items open stub pages titled in Russian.
Definition of Done: a full search from the browser tab runs through the real runner and cards appear live; Pause/Stop work; reload keeps state; JS console errors = 0 (check with one Playwright smoke test that loads the page and reads console errors); screenshot at 1440x900 saved to debug/ui_search.png and described in 5 lines in PROGRESS.md; ruff clean.
DONE -> commit, log in PROGRESS.md, go straight to the next stage.

## STAGE 7 - Base, lead drawer, export

Read: SPEC sections 2, 7.
Build: 'База' view (same grid, status filter and status change in bulk), lead drawer per SPEC 7 (contacts, Leaflet map with offline fallback, source links, notes autosave, prev/next navigation), bulk delete with confirm, export of selected or filtered leads to CSV and XLSX (openpyxl) with Russian column headers.
Definition of Done: drawer opens from any card and keyboard Esc closes it; status changes persist; export opens correctly in Excel (UTF-8 BOM for CSV); tests for filters and export; ruff clean.
DONE -> commit, log in PROGRESS.md, go straight to the next stage.

## STAGE 8 - Website enrichment and flags

Read: SPEC sections 2, 3.
Build: enrich/site.py (httpx, timeouts 8 s, max 2 MB, same-domain pages: main, /contacts, /kontakty, 'контакты' link only, max 3 pages per site, concurrency 5, respects stop event) extracting emails, phones, social links; enrich/socials.py (normalize Instagram, Telegram, WhatsApp, Viber, VK, Facebook, YouTube links); enrich/template_detect.py (site builder detection by domain and generator meta/markers: Tilda, Wix, Nethouse, uKit, Jimdo, Squarespace, WordPress.com, setup.shop and similar; returns template_name). Flags: no_site (no website and no socials), only_socials (website is a social/linktree/taplink page or only socials exist), template_site. Run enrichment as a job step after dedupe, with its own progress and a manual 'Обогатить выбранные' action.
Definition of Done: unit tests on saved HTML samples (tests/fixtures/sites) for each flag and each social normalizer; a dead site or timeout never fails the job; ruff clean.
DONE -> commit, log in PROGRESS.md, go straight to the next stage.

## STAGE 9 - Outreach: prompt builder, channels, messages

Read: SPEC sections 2, 7, 8.
Build: page 'ИИ' as a prompt constructor with no model calls (my_offer text, tone, length, editable prompt templates with variables, live preview on a sample lead); in the drawer: 'Собрать промпт' + 'Скопировать промпт', 'Текст сообщения' textarea for the pasted answer, 'Тема письма', channel buttons per SPEC 8 (WhatsApp, Telegram, Instagram, Viber, Email via mailto, Call), 'Отметить отправленным', 'Ответили'; batch prompt export for selected leads (.md download); static message templates CRUD with a default per flag; pages 'Сообщения' (leads with conversation state, status filters) and 'Чаты' (per-lead timeline); page 'Отбор' (saved filter presets: flag, city, category, rating range, has phone/email/socials) feeding the Parser/Base lists.
Definition of Done: tests for prompt rendering (every variable, missing fields never print 'None'), link generation for phones, usernames, emails with URL-encoding and Cyrillic, disabled buttons for missing channels, status transitions, batch export; e2e covers the flow card -> prompt -> paste -> link -> mark sent; ruff clean.
DONE -> commit, log in PROGRESS.md, go straight to the next stage.

## STAGE 10 - Charts, hotkeys, settings, profile, help

Read: SPEC sections 6, 7.
Build: 'Графики' (vendored Chart.js): leads per day, per source, per flag, funnel by status, top cities and categories; 'Клавиши': list and rebinding stored in settings, defaults: / focus search, J/K next/prev card, B add to base, Enter open drawer, Esc close, S start search; 'Настройки' for every setting in SPEC 6; 'Профиль' with local name, avatar upload and stats; 'Помощь' with a short static guide in Russian.
Definition of Done: every setting persists and takes effect without restart; hotkeys do not fire while typing in inputs; ruff clean.
DONE -> commit, log in PROGRESS.md, go straight to the next stage.

## STAGE 11 - Hub: module registry, dashboard, logs, queue, supervisor

Read: SPEC sections 1, 6, 9.
Build per SPEC 9: hub/registry.py (module interface, 'leads' registered, placeholders hh/habr/freelance marked 'скоро'), hub/queue.py (persistent sequential queue), hub/supervisor.py (restart with exponential backoff, max 5 per hour, graceful shutdown, browser context recycling hook), hub/metrics.py (psutil CPU/RAM/disk, nvidia-smi if present, Ollama /api/ps with timeout 2 s and a friendly offline state), page 'Дашборд' as the first rail item with module cards, Start/Stop/'В очередь', system load, Ollama card, live per-module log tail (SSE, level filter); per-module rotating logs in logs/<module>.log.
Definition of Done: tests for queue order and persistence across restart, supervisor backoff with a crashing fake module, log tail SSE, metrics with psutil mocked, dashboard renders when Ollama is down and when nvidia-smi is missing; UI smoke test for the dashboard; ruff clean.
DONE -> commit, log in PROGRESS.md, go straight to the next stage.

## STAGE 12 - Hardening and final acceptance

Read: PROGRESS.md, DECISIONS.md, SPEC sections 7, 9.
Do:
1. Hardening: run.bat from a clean clone works end to end; graceful shutdown (stop worker, close browser); DB backup on start (keep last 5); log rotation; a 'Диагностика' page listing failed pairs (SourceChanged) with debug snapshot paths; README.md (15 lines: install, run, data folders, how to run tests).
2. Run `pytest -q` with coverage; fix real failures; ruff clean.
3. Live tests (-m live): each source for 'барбершоп' in Саратов (max 20) with a per-source field-coverage table, then the full cycle from the Testing standard. Save results in FINAL_REPORT.md.
4. UI check: screenshot every page at 1440x900 to debug/ui/, compare with docs/reference (view each image at most once), fix mismatches in at most 2 polish passes.
5. Walk through SPEC sections 1-9 and write a pass/fail checklist into FINAL_REPORT.md; fix failures where possible by the failure ladder.
6. FINAL_REPORT.md contains: what works, test and coverage numbers, live results per source, KNOWN_ISSUES with evidence, how to run. Commit.
7. Send the one final message to the user (15 lines max). Done.