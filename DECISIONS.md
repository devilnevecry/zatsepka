# DECISIONS

## Stage 0 - research (environment + GeoLeadScraper hints)
- Env: Python 3.12.10, git 2.56, Chrome installed (C:\Program Files\Google\Chrome\Application\chrome.exe), Playwright chromium already present. Network to github works.
- GeoLeadScraper cloned to docs/ref_geoleadscraper (gitignored). Used ONLY as field-path hints, no code copied.
- Google hint: results XHR (search?tbm=map, pb param) returns )]}'-prefixed JSON, field 'd' is a JSON string; each place = arr[0][1][i][14]; paths: name[11], address[39], cid[10], place_id[78], rating[4][7], reviews[4][8], price[4][2], phone[178][0][3], website[7][0], lat[9][2], lon[9][3], photos[37][1], categories[13], hours[203][0], attributes[100][1], addr components[183][1], description[161][1].
- Yandex hint: page embeds <script type="application/json" class="state-view">; org item at stack[0].results.items[0]: title, address/compositeAddress, coordinates[lat,lon], ratingData.ratingValue/ratingCount, workingTimeText, photos.count, categories[].name, features[].name, urls[], phones[].value, socialLinks[].href. List container .search-list-view__list > li, scroller .scroll__container.
- 2GIS hint: page embeds var initialState = JSON.parse('...'); data.search.profile -> query/total/pages; data.entity.profile[id].data -> name, address_name, point.lat/lon, reviews.general_rating/general_review_count, contact_groups[].contacts[] {type,text}, rubrics[].name, schedule.<day>.working_hours, attribute_groups[].attributes[].name, external_content[0].count. Pagination via /page/N.
- Default ambiguity resolutions: project root = repo root (no nested rozvedka/ dir); forms use urlencoded/JSON (no python-multipart, avatar via base64 JSON); vendored libs downloaded once at build time, app never references CDN at runtime.
