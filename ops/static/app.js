"use strict";

const byId = (id) => document.getElementById(id);
const formatter = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 });
const dateFormatter = new Intl.DateTimeFormat("id-ID", {
  day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
});
const signalLabels = {
  sales_spike: "Lonjakan penjualan",
  stock_gap: "Selisih stok",
  sensor_exception: "Pembacaan sensor di atas acuan",
};
const qualityLabels = {
  duplicate: "Catatan ganda",
  missing_sensor: "Pembacaan sensor kosong",
};
const state = {
  dashboard: null,
  dashboardRequest: null,
  prompts: [],
  draftPending: false,
};

function node(tag, content, className) {
  const element = document.createElement(tag);
  if (content !== undefined) element.textContent = content;
  if (className) element.className = className;
  return element;
}

function status(id, text = "", error = false) {
  const element = byId(id);
  element.textContent = text;
  element.classList.toggle("error", error);
}

function number(value, unit = "") {
  return value == null ? "—" : formatter.format(value) + unit;
}

function displayDate(day) {
  return dateFormatter.format(new Date(day + "T00:00:00Z"));
}

function assertDates() {
  const end = byId("end");
  end.setCustomValidity(
    byId("start").value > end.value ? "Tanggal akhir harus sama dengan atau setelah tanggal mulai." : "",
  );
}

async function api(path, options) {
  const response = await fetch(path, options);
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error("Respons layanan tidak dapat dibaca.");
  }
  if (!response.ok) {
    throw new Error(typeof body.error === "string" ? body.error : "Permintaan gagal.");
  }
  return body;
}

function refreshDraftAvailability() {
  byId("draft-submit").disabled = state.draftPending || !state.dashboard?.totals.days;
}

function renderTrend() {
  const chart = byId("trend");
  chart.replaceChildren();
  const metric = byId("chart-metric").value;
  const rows = state.dashboard?.weekly || [];
  if (!rows.length) {
    chart.append(node("p", "Tidak ada nilai mingguan dalam rentang ini.", "note"));
    return;
  }
  const maximum = Math.max(1, ...rows.map((row) => row[metric] || 0));
  for (const { week, [metric]: value } of rows) {
    const row = node("div", undefined, "chart-row");
    const track = node("span", undefined, "bar-track");
    const fill = node("span", undefined, "bar-fill");
    track.setAttribute("aria-hidden", "true");
    fill.style.width = `${value == null ? 0 : (value / maximum) * 100}%`;
    track.append(fill);
    row.append(node("span", week), track, node("span", number(value), "chart-value"));
    chart.append(row);
  }
}

function renderSignals(dataset) {
  status("source-record");
  const signals = byId("signals");
  signals.replaceChildren();
  for (const item of dataset.signals) {
    const row = node("tr");
    const source = node("button", "S" + item.id, "source-button");
    source.type = "button";
    source.setAttribute("aria-label", "Lihat catatan sumber S" + item.id);
    source.addEventListener("click", async () => {
      status("source-record", "Memuat catatan sumber...");
      try {
        const data = await api("/api/source?id=" + item.id);
        if (!source.isConnected) return;
        status("source-record", `S${data.id} · ${data.site} · ${displayDate(data.day)} · Penjualan ${number(data.sales)} unit · Stok buku ${number(data.book_stock)} unit · Stok fisik ${number(data.counted_stock)} unit · Sensor ${number(data.sensor)}`);
      } catch (error) {
        if (source.isConnected) status("source-record", error.message, true);
      }
    });
    row.append(node("td"));
    row.firstChild.append(source);
    const values = [
      displayDate(item.day), item.site,
      signalLabels[item.kind] || item.kind, number(item.actual), number(item.reference),
    ];
    for (const value of values) row.append(node("td", value));
    signals.append(row);
  }
  if (!dataset.signals.length) {
    const row = node("tr");
    const cell = node("td", "Tidak ada anomali dalam rentang ini.");
    cell.colSpan = 6;
    row.append(cell);
    signals.append(row);
  }

  const quality = byId("quality");
  quality.replaceChildren();
  for (const item of dataset.quality) {
    const entry = node("li");
    entry.append(
      node("strong", qualityLabels[item.issue] || item.issue),
      node("p", `${item.site} · ${displayDate(item.day)}`),
    );
    quality.append(entry);
  }
  if (!dataset.quality.length) quality.append(node("li", "Tidak ada masalah yang tercatat dalam rentang ini."));
}

function renderDashboard(dataset) {
  const { totals } = dataset;
  byId("metric-sales").textContent = number(totals.sales, " unit");
  byId("metric-days").textContent = number(totals.days);
  byId("metric-stock").textContent = number(totals.stock_gap, " unit");
  byId("metric-sensor").textContent = number(totals.avg_sensor);
  const scope = `${dataset.site} · ${displayDate(dataset.start)} – ${displayDate(dataset.end)}`;
  byId("draft-scope").textContent = "Cakupan draf: " + scope;
  status(
    "dashboard-status",
    totals.days ? "Filter aktif: " + scope : "Tidak ada catatan untuk filter aktif: " + scope,
  );
  renderTrend();
  renderSignals(dataset);
  const sourceSelect = byId("draft-source");
  const previousSource = sourceSelect.value;
  const all = node("option", "Semua bukti dalam filter aktif");
  all.value = "";
  sourceSelect.replaceChildren(all);
  for (const item of dataset.signals) {
    const id = "S" + item.id;
    const option = node("option", `${id} · ${item.site} · ${signalLabels[item.kind]}`);
    option.value = id;
    sourceSelect.append(option);
  }
  if (Array.from(sourceSelect.options).some((option) => option.value === previousSource)) {
    sourceSelect.value = previousSource;
  }
  const distribution = byId("distribution");
  distribution.replaceChildren();
  for (const [key, label] of [["sales", "Penjualan (unit)"], ["stock", "Selisih stok absolut (unit)"], ["sensor", "Sensor"]]) {
    const stats = ["min", "mean", "max"].map((part) => number(dataset.distribution[key + "_" + part]));
    const entry = node("li");
    entry.append(node("strong", label), node("p", `Minimum ${stats[0]} · Rata-rata ${stats[1]} · Maksimum ${stats[2]}`));
    distribution.append(entry);
  }
  refreshDraftAvailability();
}

async function loadDashboard() {
  state.dashboardRequest?.abort();
  const controller = new AbortController();
  state.dashboardRequest = controller;
  const params = new URLSearchParams(new FormData(byId("filter-form")));
  status("dashboard-status", "Memuat data...");
  try {
    const dataset = await api("/api/dashboard?" + params, { signal: controller.signal });
    if (controller.signal.aborted) return;
    state.dashboard = dataset;
    byId("draft-result").hidden = true;
    renderDashboard(dataset);
  } catch (error) {
    if (!controller.signal.aborted) {
      const suffix = state.dashboard ? " Filter sebelumnya masih aktif." : "";
      status("dashboard-status", error.message + suffix, true);
    }
  }
}

function usePrompt(prompt) {
  const select = byId("task");
  select.value = prompt.id;
  select.focus();
}

async function copyPrompt(prompt) {
  try {
    if (!navigator.clipboard) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(prompt.template);
    status("prompt-status", "Templat disalin.");
  } catch {
    status("prompt-status", "Buka bagian templat untuk menyalinnya secara manual.", true);
  }
}

function renderPrompts() {
  const query = byId("prompt-search").value.trim().toLocaleLowerCase("id-ID");
  const list = byId("prompt-list");
  list.replaceChildren();
  for (const prompt of state.prompts) {
    const searchable = [prompt.title, prompt.description, prompt.audience, prompt.instructions].join(" ");
    if (!searchable.toLocaleLowerCase("id-ID").includes(query)) continue;
    const details = node("details");
    const content = node("div", undefined, "prompt-details");
    for (const [label, value] of [
      ["Tujuan", prompt.description], ["Untuk", prompt.audience],
      ["Instruksi", prompt.instructions], ["Contoh", prompt.example],
      ["Periksa sebelum digunakan", prompt.review],
    ]) {
      const paragraph = node("p");
      paragraph.append(node("strong", label + " "), document.createTextNode(value));
      content.append(paragraph);
    }
    const template = node("details");
    template.append(node("summary", "Templat lengkap"), node("pre", prompt.template, "prompt-template"));
    content.append(template);
    const copy = node("button", "Salin templat", "secondary");
    copy.type = "button";
    copy.addEventListener("click", () => copyPrompt(prompt));
    const use = node("button", "Pilih untuk draf");
    use.type = "button";
    use.addEventListener("click", () => usePrompt(prompt));
    content.append(copy, use);
    details.append(node("summary", prompt.title), content);
    list.append(details);
  }
  if (!list.children.length) list.append(node("p", "Tidak ada prompt yang cocok.", "note"));
}

async function loadPrompts() {
  try {
    state.prompts = await api("/api/prompts");
    for (const prompt of state.prompts) {
      const option = node("option", prompt.title);
      option.value = prompt.id;
      byId("task").append(option);
    }
    renderPrompts();
  } catch (error) {
    status("prompt-status", error.message, true);
  }
}

async function submitDraft(event) {
  event.preventDefault();
  if (!state.dashboard?.totals.days || state.draftPending) return;
  const form = new FormData(event.currentTarget);
  const { site, start, end } = state.dashboard;
  state.draftPending = true;
  refreshDraftAvailability();
  byId("draft-result").hidden = true;
  status("draft-status", "Menyusun draf lokal...");
  try {
    const draft = await api("/api/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: form.get("prompt"), brief: form.get("brief"), source: form.get("source"), site, start, end }),
    });
    if (site !== state.dashboard.site || start !== state.dashboard.start || end !== state.dashboard.end
        || form.get("source") !== byId("draft-source").value) {
      status("draft-status", "Filter berubah. Buat draf baru untuk cakupan aktif.");
      return;
    }
    const references = byId("draft-evidence");
    references.replaceChildren();
    for (const [key, value] of Object.entries(draft.evidence)) {
      references.append(node("li", `${key} · ${value}`));
    }
    byId("draft-output").textContent = draft.text;
    byId("draft-result").hidden = false;
    const warning = draft.has_valid_citations ? "" : " Draf belum memiliki kutipan sumber yang dapat diperiksa.";
    status("draft-status", `Draf siap ditinjau. Cakupan: ${site} · ${displayDate(start)} – ${displayDate(end)}.${warning}`);
  } catch (error) {
    status("draft-status", error.message, true);
  } finally {
    state.draftPending = false;
    refreshDraftAvailability();
  }
}

function renderWorkflowList(id, items, detailKey) {
  const list = byId(id);
  list.replaceChildren();
  for (const item of items) {
    const entry = node("li");
    entry.append(
      node("strong", item.title),
      node("p", `${item.owner} · ${item.status}`),
      node("p", item[detailKey]),
    );
    list.append(entry);
  }
}

async function loadWorkflow() {
  try {
    const workflow = await api("/api/workflow");
    renderWorkflowList("requests", workflow.requests, "acceptance");
    renderWorkflowList("risks", workflow.risks, "evidence");
    renderWorkflowList("programs", workflow.programs, "due");
    const { subject, message, owner, status: draftStatus } = workflow.escalation;
    byId("escalation").append(
      node("strong", subject), node("p", `${owner} · ${draftStatus}`, "detail"), node("p", message),
    );
  } catch (error) {
    status("workflow-status", error.message, true);
  }
}

byId("filter-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (event.currentTarget.reportValidity()) loadDashboard();
});
byId("start").addEventListener("input", assertDates);
byId("end").addEventListener("input", assertDates);
byId("chart-metric").addEventListener("change", renderTrend);
byId("prompt-search").addEventListener("input", renderPrompts);
byId("draft-source").addEventListener("change", () => {
  byId("draft-result").hidden = true;
  status("draft-status");
});
byId("draft-form").addEventListener("submit", submitDraft);

assertDates();
loadDashboard();
loadPrompts();
loadWorkflow();
