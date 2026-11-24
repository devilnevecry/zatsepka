# DECISIONS

## Stage 0 - research (environment + GeoLeadScraper hints)
- Env: Python 3.12.10, git 2.56, Chrome installed (C:\Program Files\Google\Chrome\Application\chrome.exe), Playwright chromium already present. Network to github works.
- GeoLeadScraper cloned to docs/ref_geoleadscraper (gitignored). Used ONLY as field-path hints, no code copied.
- Google hint: results XHR (search?tbm=map, pb param) returns )]}'-prefixed JSON, field 'd' is a JSON string; each place = arr[0][1][i][14]; paths: name[11], address[39], cid[10], place_id[78], rating[4][7], reviews[4][8], price[4][2], phone[178][0][3], website[7][0], lat[9][2], lon[9][3], photos[37][1], categories[13], hours[203][0], attributes[100][1], addr components[183][1], description[161][1].
- Yandex hint: page embeds <script type="application/json" class="state-view">; org item at stack[0].results.items[0]: title, address/compositeAddress, coordinates[lat,lon], ratingData.ratingValue/ratingCount, workingTimeText, photos.count, categories[].name, features[].name, urls[], phones[].value, socialLinks[].href. List container .search-list-view__list > li, scroller .scroll__container.
- 2GIS hint: page embeds var initialState = JSON.parse('...'); data.search.profile -> query/total/pages; data.entity.profile[id].data -> name, address_name, point.lat/lon, reviews.general_rating/general_review_count, contact_groups[].contacts[] {type,text}, rubrics[].name, schedule.<day>.working_hours, attribute_groups[].attributes[].name, external_content[0].count. Pagination via /page/N.
- Default ambiguity resolutions: project root = repo root (no nested rozvedka/ dir); forms use urlencoded/JSON (no python-multipart, avatar via base64 JSON); vendored libs downloaded once at build time, app never references CDN at runtime.

## Stage 1 - default resolutions
- Forms upload: JSON/base64 (no python-multipart dependency needed); avatar stored as data URL string.
- / route = stub index (full UI at stage 6); run.py pre-checks port 8000 before uvicorn starts.
- Capture tool keeps its own BrowserManager + lock path (module constants overridable for tests).
- Selectolax HTML outline uses child/next traversal, filters non-aria/data attrs and hashes classes.
- Health TestClient via create_app() factory (module-level app not used in tests).

## Stage 2 - Google findings (DECISIONS, from GeoLeadScraper hints + capture run)
- Extraction priority per source: (1) JSON responses the page fetches, (2) embedded page state, (3) DOM; hashes CSS classes avoided, aria/data anchors preferred.
- Google list data: XHR search?tbm=map with pb param; response cleaned of `)]}'` and JSON.parsed; `d` -> items; each place el[14]; name=el[11], address=el[39], cid=el[10], place_id=el[78], rating=el[4][7], reviews=el[4][8], price=el[4][2], phone=el[178][0][3], website=el[7][0], lat=el[9][2], lon=el[9][3], photos=el[37][1], categories=el[13], hours=el[203][0], attributes=el[100][1], description=el[161][1].
- Google scroll pitfall: window scrolling does nothing; scroll `[role=feed]` via mouse.wheel(0, 3000) after hover-center, wait up to 4s for count growth; stop after 3 scrolls w/o new items or end marker.
- Block markers: url (sorry/index, sorry/captcha, consent.google.com), title (unusual traffic), text (unusual traffic / captcha phrases) -> NeedsHuman.

## Stage 3 - Yandex findings
- Search URL: https://yandex.ru/maps/?text=<query>+<city> (captures 20261123_171656 and _171738 saved results.html + XHR responses).
- List anchors: `.search-list-view__list a[href*='/maps/org/']`; virtualized scroller `.scroll__container`; single result page state in `<script type="application/json" class="state-view">` with stack[0].results.items[]; both direct item and item.result shapes handled.
- Fields per org: title, address/compositeAddress.street, coordinates[lat,lon], ratingData.ratingValue/ratingCount, workingTimeText, photos.count, categories[].name, features[].name, urls[0], phones[].value, socialLinks[].href.
- Captcha markers: url showcaptcha/captcha.yandex/passport.yandex, text 'Подтвердите, что запросы отправляли вы' -> NeedsHuman.

## Stage 4 - 2GIS findings
- Search URL https://2gis.ru/<city_slug>/search/<query>; city slugs saratov/engels; base domain configurable via settings.
- Catalog API items (captured responses): result.items[] with id, name, address_name, rubrics[].name, point.lat/lon, reviews.general_rating/general_review_count, contact_groups[].contacts[] {type,text}, attribute_groups[].attributes[].name, external_content[0].count.
- Page state embedded as `var initialState = JSON.parse('...')`; detail page saved to tests/fixtures/twogis/detail.html.
- KNOWN ISSUE: live scrape of 'барбершоп' Saratov returns 12 unique firms (2 attempts, internal scroller fix) - below 15-row DoD; source exposes only 12 for that query; recorded for FINAL_REPORT.md.
