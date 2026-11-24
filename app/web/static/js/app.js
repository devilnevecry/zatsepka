// Frontend behavior: settings, chips, estimate, job controls, SSE, cards, drawer, theme, hotkeys.

(() => {
  "use strict";

  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));
  const state = { settings: null, jobId: null, tab: "parser", leads: [], selected: new Set(), source: null };

  async function api(path, options = {}) {
    const resp = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!resp.ok) throw new Error(`${path}: ${resp.status}`);
    return resp.json();
  }

  function savedTheme() {
    try { return localStorage.getItem("rozvedka-theme") || "dark"; } catch { return "dark"; }
  }

  function applyTheme(theme) {
    document.body.classList.toggle("theme-dark", theme === "dark");
    document.body.classList.toggle("theme-light", theme === "light");
    const label = $(".theme-label");
    if (label) label.textContent = theme === "dark" ? "Ночь" : "День";
    try { localStorage.setItem("rozvedka-theme", theme); } catch { /* ignore */ }
  }

  function renderChips(container, values, kind) {
    container.innerHTML = values.map((v, i) =>
      `<span class="chip" data-index="${i}">${escapeHtml(v)}<button type="button" data-remove="${kind}" data-index="${i}" aria-label="Удалить ${escapeHtml(v)}">×</button></span>`
    ).join("");
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function saveSettings(patch) {
    state.settings = await api("/api/settings", { method: "POST", body: JSON.stringify(patch) });
    renderChips($("#city-chips"), state.settings.cities, "city");
    renderChips($("#category-chips"), state.settings.categories, "category");
    await refreshEstimate();
  }

  async function refreshEstimate() {
    try {
      const est = await api("/api/estimate");
      $("#estimate-box").textContent =
        `${len(state.settings.cities)} городов × ${len(state.settings.categories)} категорий = ${est.pairs_total} пар\n` +
        `уже искали — пропустим ${est.pairs_skipped}, осталось ${est.pairs_to_run}, примерно ${est.approx_minutes} мин`;
    } catch (e) { $("#estimate-box").textContent = "Оценка недоступна"; }
  }

  function len(a) { return Array.isArray(a) ? a.length : 0; }

  function flagOf(lead) {
    const f = lead.flags || {};
    if (f.no_site) return ["Без сайта", "flag-no_site"];
    if (f.only_socials) return ["Только соцсети", "flag-only_socials"];
    if (f.template_site) return ["Шаблон", "flag-template_site"];
    if (lead.status === "waiting_reply") return ["Ждёт ответа", "flag-waiting_reply"];
    if (f.chain_count) return [`${f.chain_count} компаний`, "flag-chain"];
    return ["", ""];
  }

  function channelButton(name, url, present) {
    const icons = { instagram: "◎", telegram: "➤", viber: "V", whatsapp: "W" };
    const cls = `channel-btn ch-${name}${present ? "" : " disabled"}`;
    return `<a class="${cls}" href="${present ? escapeHtml(url) : "#"}" target="_blank" rel="noopener" title="${name}" data-channel="${name}">${icons[name] || "•"}</a>`;
  }

  function socialUrl(lead, name) {
    const s = lead.socials || {};
    if (s[name]) return s[name];
    if (name === "whatsapp" && lead.phones && lead.phones[0]) return `https://wa.me/${lead.phones[0].replace(/\D/g, "")}`;
    return "#";
  }

  function hasChannel(lead, name) {
    if ((lead.socials || {})[name]) return true;
    return name === "whatsapp" && (lead.phones || []).length > 0;
  }

  function cardHtml(lead) {
    const [flagText, flagCls] = flagOf(lead);
    const cityCat = `${lead.city || "—"} · ${lead.category || "—"}`;
    return `<article class="lead-card" data-lead-id="${lead.id}" tabindex="0">
      <input class="card-check" type="checkbox" data-select="${lead.id}" ${state.selected.has(lead.id) ? "checked" : ""} aria-label="Выбрать ${escapeHtml(lead.name)}">
      <div class="card-top">
        ${flagText ? `<span class="flag-pill ${flagCls}">${flagText}</span>` : ""}
        <span class="rating-chip" title="Рейтинг">★ ${lead.rating || "—"}</span>
      </div>
      <div class="card-name" title="${escapeHtml(lead.name)}">${escapeHtml(lead.name)}</div>
      <div class="card-meta">📍 ${escapeHtml(cityCat)}</div>
      <div class="card-map" aria-hidden="true"></div>
      <div class="card-bottom">
        ${channelButton("instagram", socialUrl(lead, "instagram"), hasChannel(lead, "instagram"))}
        ${channelButton("telegram", socialUrl(lead, "telegram"), hasChannel(lead, "telegram"))}
        ${channelButton("viber", socialUrl(lead, "viber"), hasChannel(lead, "viber"))}
        ${channelButton("whatsapp", socialUrl(lead, "whatsapp"), hasChannel(lead, "whatsapp"))}
        <button class="to-base" type="button" data-to-base="${lead.id}">+ В базу</button>
      </div>
    </article>`;
  }

  function renderCards() {
    const grid = $("#card-grid");
    if (!grid) return;
    grid.innerHTML = state.leads.map(cardHtml).join("");
    $("#shown-line").textContent = `Показано ${state.leads.length} из ${state.leads.length} лидов (в базе ${state.tab === "base" ? state.leads.length : 0})`;
  }

  async function loadLeads() {
    const params = new URLSearchParams({
      tab: state.tab,
      search: $("#global-search")?.value || "",
      city: $("#filter-city")?.value || "",
      status: $("#filter-status")?.value || "",
    });
    state.leads = await api(`/api/leads?${params}`);
    renderCards();
    await refreshCounts();
  }

  async function refreshCounts() {
    try {
      const c = await api("/api/counts");
      $("#count-parser").textContent = c.parser;
      $("#count-base").textContent = c.base;
      $("#count-messages").textContent = c.messages;
    } catch { /* ignore */ }
  }

  function openDrawer(lead) {
    state.source = lead;
    const drawer = $("#drawer");
    drawer.innerHTML = `
      <div class="drawer-nav"><button type="button" data-drawer-prev>‹</button>
        <span>${lead.name}</span><button type="button" data-drawer-close aria-label="Закрыть">✕</button></div>
      <h2>${escapeHtml(lead.name)}</h2>
      <div class="drawer-section"><h3>Контакты</h3>
        <div>Телефоны: ${escapeHtml((lead.phones || []).join(", ") || "—")}</div>
        <div>Email: ${escapeHtml((lead.emails || []).join(", ") || "—")}</div>
        <div>Сайт: ${escapeHtml(lead.website || "—")}</div>
      </div>
      <div class="drawer-section"><h3>Карта</h3><div id="drawer-map" style="height:180px;border-radius:12px;background:var(--surface);background-image:radial-gradient(circle,var(--muted) 1px,transparent 1px);background-size:12px 12px"></div></div>
      <div class="drawer-section"><h3>Источники</h3>${Object.entries(lead.maps || {}).map(([k, v]) => `<a href="${escapeHtml(v.url)}" target="_blank" rel="noopener">${escapeHtml(k)}</a>`).join(" ") || "—"}</div>
      <div class="drawer-section"><h3>Заметки</h3><textarea id="drawer-notes" rows="3" style="width:100%">${escapeHtml(lead.notes || "")}</textarea></div>
      <div class="drawer-section"><h3>Сообщение</h3>
        <div class="drawer-nav"><button type="button" data-channel-open="telegram">Telegram</button><button type="button" data-channel-open="whatsapp">WhatsApp</button><button type="button" data-channel-open="instagram">Instagram</button><button type="button" data-channel-open="call">Позвонить</button></div>
        <button id="build-prompt" class="btn-secondary" type="button">Собрать промпт</button>
        <textarea id="message-text" rows="4" style="width:100%" placeholder="Текст сообщения"></textarea>
        <button id="mark-sent" class="btn-primary" type="button">Отметить отправленным</button>
      </div>`;
    drawer.classList.remove("hidden");
    $("#drawer-backdrop").classList.remove("hidden");
    $("#drawer-notes").addEventListener("change", e => api(`/api/leads/${lead.id}/notes`, { method: "POST", body: JSON.stringify({ notes: e.target.value }) }));
    if (lead.lat && lead.lon && window.L) {
      try {
        const map = L.map("drawer-map").setView([lead.lat, lead.lon], 15);
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "OSM" }).addTo(map);
        L.marker([lead.lat, lead.lon]).addTo(map);
      } catch { /* offline fallback: dot grid already visible */ }
    }
  }

  function closeDrawer() {
    $("#drawer").classList.add("hidden");
    $("#drawer-backdrop").classList.add("hidden");
  }

  function openChannel(lead, channel) {
    if (!lead) return;
    let url = "";
    const digits = (lead.phones?.[0] || "").replace(/\D/g, "");
    if (channel === "telegram") {
      const user = (lead.socials || {}).telegram;
      url = user ? user : digits ? `https://t.me/${digits}` : "";
    } else if (channel === "whatsapp" && digits) {
      url = `https://wa.me/${digits}`;
    } else if (channel === "instagram" && lead.socials?.instagram) {
      url = lead.socials.instagram;
    } else if (channel === "call" && digits) {
      url = `tel:+${digits}`;
    }
    if (url) window.open(url, "_blank", "noopener");
  }

  function connectSse(jobId) {
    const src = new EventSource(`/api/jobs/${jobId}/events`);
    src.addEventListener("lead", async e => {
      const data = JSON.parse(e.data);
      if (state.tab !== "parser") return;
      const lead = await api(`/api/leads/${data.id}`);
      if (lead && lead.id) {
        state.leads.unshift(lead);
        renderCards();
      }
    });
    src.addEventListener("needs_human", e => {
      const banner = $("#banner");
      banner.textContent = "Нужно ваше участие в окне браузера";
      banner.classList.remove("hidden");
    });
    src.addEventListener("done", () => { loadLeads(); src.close(); });
    src.addEventListener("error", () => { /* SSE reconnects automatically */ });
  }

  async function init() {
    applyTheme(savedTheme());
    $("#theme-toggle")?.addEventListener("click", () => {
      const next = document.body.classList.contains("theme-dark") ? "light" : "dark";
      applyTheme(next);
    });

    if (!$("#card-grid")) return;

    state.settings = await api("/api/settings");
    if (window.location.pathname.includes("/page/base")) state.tab = "base";
    renderChips($("#city-chips"), state.settings.cities, "city");
    renderChips($("#category-chips"), state.settings.categories, "category");
    $("#skip-days").value = state.settings.skip_days;
    $("#no-repeat").checked = !!state.settings.no_repeat;
    $("#pause-min").value = state.settings.pause_min;
    $("#pause-max").value = state.settings.pause_max;
    $("#max-results").value = state.settings.max_results_per_pair;
    $("#max-minutes").value = state.settings.max_minutes;
    $$("[data-source]").forEach(el => { el.checked = !!state.settings.sources[el.dataset.source]; });
    await refreshEstimate();
    await loadLeads();
    refreshCounts();

    document.addEventListener("click", e => {
      const remove = e.target.closest("[data-remove]");
      if (remove) {
        const key = remove.dataset.remove;
        const idx = Number(remove.dataset.index);
        const next = [...state.settings[key]];
        next.splice(idx, 1);
        saveSettings({ [key]: next });
        return;
      }
      const tab = e.target.closest("[data-tab]");
      if (tab) {
        $$(".pill").forEach(p => p.classList.remove("active"));
        tab.classList.add("active");
        state.tab = tab.dataset.tab;
        loadLeads();
        return;
      }
      const toBase = e.target.closest("[data-to-base]");
      if (toBase) {
        const id = Number(toBase.dataset.toBase);
        api(`/api/leads/${id}/status`, { method: "POST", body: JSON.stringify({ status: "in_base" }) }).then(loadLeads);
        return;
      }
      if (e.target.closest("[data-drawer-close]") || e.target.id === "drawer-backdrop") { closeDrawer(); return; }
      if (e.target.closest("[data-drawer-prev]")) {
        const idx = state.leads.findIndex(l => l.id === state.source?.id);
        if (idx > 0) openDrawer(state.leads[idx - 1]);
        return;
      }
      const channel = e.target.closest("[data-channel-open]");
      if (channel) { openChannel(state.source, channel.dataset.channelOpen); return; }
      const card = e.target.closest(".lead-card");
      if (card && !e.target.closest("button,a,input")) {
        const lead = state.leads.find(l => l.id === Number(card.dataset.leadId));
        if (lead) openDrawer(lead);
      }
    });

    document.addEventListener("change", e => {
      const sel = e.target.closest("[data-select]");
      if (sel) {
        const id = Number(sel.dataset.select);
        if (sel.checked) state.selected.add(id); else state.selected.delete(id);
      }
    });

    $("#city-add")?.addEventListener("click", () => {
      const v = $("#city-input").value.trim();
      if (v && !state.settings.cities.includes(v)) saveSettings({ cities: [...state.settings.cities, v] });
      $("#city-input").value = "";
    });
    $("#category-add")?.addEventListener("click", () => {
      const v = $("#category-input").value.trim();
      if (v && !state.settings.categories.includes(v)) saveSettings({ categories: [...state.settings.categories, v] });
      $("#category-input").value = "";
    });
    $("#category-all")?.addEventListener("click", () => saveSettings({ categories: ["барбершоп", "салон красоты", "кофейня", "стоматология", "автосервис", "фитнес-клуб"] }));
    $("#skip-days")?.addEventListener("change", e => saveSettings({ skip_days: Number(e.target.value) }));
    $("#no-repeat")?.addEventListener("change", e => saveSettings({ no_repeat: e.target.checked }));
    $("#max-results")?.addEventListener("change", e => saveSettings({ max_results_per_pair: Number(e.target.value) }));
    $("#max-minutes")?.addEventListener("change", e => saveSettings({ max_minutes: Number(e.target.value) }));
    $$("[data-source]").forEach(el => el.addEventListener("change", () => {
      const sources = {};
      $$("[data-source]").forEach(x => sources[x.dataset.source] = x.checked);
      saveSettings({ sources });
    }));

    $("#start-btn")?.addEventListener("click", async () => {
      const sources = {};
      $$("[data-source]").forEach(x => sources[x.dataset.source] = x.checked);
      const resp = await api("/api/jobs", { method: "POST", body: JSON.stringify({
        sources,
        no_repeat: $("#no-repeat").checked,
        skip_days: Number($("#skip-days").value),
        max_results_per_pair: Number($("#max-results").value),
        max_minutes: Number($("#max-minutes").value),
        force: $("#force").checked,
      }) });
      state.jobId = resp.job_id;
      $("#job-status").textContent = "Поиск запущен";
      $("#banner").classList.add("hidden");
      connectSse(resp.job_id);
    });
    $("#pause-btn")?.addEventListener("click", async () => {
      const latest = await api("/api/jobs/latest");
      if (latest.id) await api(`/api/jobs/${latest.id}/pause`, { method: "POST" });
    });
    $("#stop-btn")?.addEventListener("click", async () => {
      const latest = await api("/api/jobs/latest");
      if (latest.id) await api(`/api/jobs/${latest.id}/stop`, { method: "POST" });
    });
    $("#global-search")?.addEventListener("input", () => loadLeads());
    $("#filter-city")?.addEventListener("change", () => loadLeads());
    $("#filter-status")?.addEventListener("change", () => loadLeads());
    $("#delete-btn")?.addEventListener("click", async () => {
      if (!state.selected.size || !confirm("Удалить выбранные лиды?")) return;
      await api("/api/leads/bulk", { method: "DELETE", body: JSON.stringify({ ids: [...state.selected] }) });
      state.selected.clear();
      loadLeads();
    });
    $("#export-btn")?.addEventListener("click", async () => {
      const ids = state.selected.size ? [...state.selected] : state.leads.map(l => l.id);
      const resp = await fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids, format: "csv" }) });
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "leads.csv";
      a.click();
    });

    document.addEventListener("keydown", e => {
      const typing = /input|textarea|select/i.test(e.target.tagName || "");
      if (typing) return;
      const key = e.key.toLowerCase();
      if (key === "escape") closeDrawer();
      if (key === "/") { e.preventDefault(); $("#global-search")?.focus(); }
      if (key === "j" || key === "k") {
        const cards = $$(".lead-card");
        if (!cards.length) return;
        const idx = cards.findIndex(c => c === document.activeElement);
        const next = key === "j" ? Math.min(idx + 1, cards.length - 1) : Math.max(idx - 1, 0);
        cards[next].focus();
      }
      if (key === "b") {
        const lead = state.leads.find(l => l.id === Number(document.activeElement?.dataset?.leadId));
        if (lead) api(`/api/leads/${lead.id}/status`, { method: "POST", body: JSON.stringify({ status: "in_base" }) }).then(loadLeads);
      }
    });

    const latest = await api("/api/jobs/latest");
    if (latest.status === "running" || latest.status === "needs_human") {
      state.jobId = latest.id;
      connectSse(latest.id);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
