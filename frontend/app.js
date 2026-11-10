import { chooseForm, chartNote, formatValue, renderChart, renderTable } from "./chart.js";

const $ = (id) => document.getElementById(id);
const state = { datasets: [], selected: new Set() };

// ---- API ------------------------------------------------------------------

async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new Error("Can't reach the server. Is uvicorn running?");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail;
    throw new Error(message || `Request failed (${res.status})`);
  }
  return body;
}

// ---- Small DOM helpers ------------------------------------------------------

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** Plain text with `code` and **bold** rendered safely (no innerHTML). */
function richText(target, text) {
  for (const part of String(text).split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/)) {
    if (!part) continue;
    if (part.startsWith("`") && part.endsWith("`")) target.appendChild(el("code", null, part.slice(1, -1)));
    else if (part.startsWith("**") && part.endsWith("**")) target.appendChild(el("strong", null, part.slice(2, -2)));
    else target.appendChild(document.createTextNode(part));
  }
}

// ---- Health ---------------------------------------------------------------

async function loadHealth() {
  const badge = $("health");
  try {
    const h = await api("/health");
    const ok = Object.values(h).every((v) => v === "ok");
    badge.textContent = ok ? "Connected" : "Database issue";
    badge.className = `health ${ok ? "ok" : "bad"}`;
    badge.title = Object.entries(h).map(([k, v]) => `${k}: ${v}`).join("\n");
  } catch (e) {
    badge.textContent = "Offline";
    badge.className = "health bad";
    badge.title = e.message;
  }
}

// ---- Datasets ---------------------------------------------------------------

async function loadDatasets() {
  try {
    state.datasets = await api("/datasets");
  } catch (e) {
    setStatus($("upload-status"), e.message, "error");
    state.datasets = [];
  }
  const ids = new Set(state.datasets.map((d) => d.id));
  for (const id of state.selected) if (!ids.has(id)) state.selected.delete(id);
  renderDatasets();
  renderScope();
  renderSuggestions();
}

function renderDatasets() {
  const list = $("dataset-list");
  list.replaceChildren();
  $("dataset-count").textContent = state.datasets.length ? String(state.datasets.length) : "";

  if (!state.datasets.length) {
    list.appendChild(el("li", "empty-list", "No datasets yet. Upload a CSV to get started."));
    return;
  }

  for (const ds of state.datasets) {
    const li = el("li", "dataset-item");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = state.selected.has(ds.id);
    box.setAttribute("aria-label", `Ask about ${ds.name}`);
    box.addEventListener("change", () => {
      box.checked ? state.selected.add(ds.id) : state.selected.delete(ds.id);
      renderScope();
      renderSuggestions();
    });

    const info = el("div");
    const name = el("div", "dataset-name", ds.table_name);
    name.title = `${ds.table_name} (from ${ds.original_filename})`;
    const meta = el("div", "dataset-meta", `${formatValue(ds.row_count)} rows · ${ds.column_count} columns`);
    info.append(name, meta);

    const view = el("button", "link-button", "View");
    view.type = "button";
    view.addEventListener("click", () => openDataset(ds));

    li.append(box, info, view);
    list.appendChild(li);
  }
}

function renderScope() {
  const n = state.selected.size;
  $("scope").textContent = !state.datasets.length
    ? "No datasets yet"
    : n === 0
      ? `Asking about all ${state.datasets.length} dataset${state.datasets.length > 1 ? "s" : ""}`
      : `Asking about ${n} selected dataset${n > 1 ? "s" : ""}`;
}

function scopedDatasets() {
  return state.selected.size ? state.datasets.filter((d) => state.selected.has(d.id)) : state.datasets;
}

function renderSuggestions() {
  const box = $("suggestions");
  box.replaceChildren();
  const ds = scopedDatasets()[0];
  if (!ds) return;

  const cols = ds.profile.columns;
  const pretty = (c) => c.name.replace(/_/g, " ");
  const numeric = cols.find((c) => c.inferred_role === "numeric");
  // A good "group by" column: categorical, or the text column with the fewest distinct values.
  const category = cols.find((c) => c.inferred_role === "categorical") ||
    cols
      .filter((c) => c.inferred_role === "text" && c.unique_count > 1 && c.unique_count < ds.row_count)
      .sort((a, b) => a.unique_count - b.unique_count)[0];
  const date = cols.find((c) => c.inferred_role === "datetime");

  const ideas = [];
  if (category && numeric) ideas.push(`Which ${pretty(category)} has the highest total ${pretty(numeric)}?`);
  if (date) ideas.push(`How many rows are there per month by ${pretty(date)}?`);
  if (numeric) ideas.push(`What are the average, minimum and maximum ${pretty(numeric)}?`);
  ideas.push("Which columns have missing values, and how many?");

  for (const q of ideas.slice(0, 4)) {
    const chip = el("button", "chip", q);
    chip.type = "button";
    chip.addEventListener("click", () => {
      $("question").value = q;
      $("ask-form").requestSubmit();
    });
    box.appendChild(chip);
  }
}

function openDataset(ds) {
  $("dialog-title").textContent = ds.table_name;
  $("dialog-sub").textContent =
    `From ${ds.original_filename} · ${formatValue(ds.row_count)} rows · ${ds.column_count} columns · ` +
    `${formatValue(ds.profile.duplicate_row_count)} duplicate rows · uploaded ${new Date(ds.created_at).toLocaleString()}`;

  const table = $("profile-table");
  table.replaceChildren();
  const head = table.createTHead().insertRow();
  for (const [label, cls] of [["Column"], ["Type"], ["Missing", "num"], ["Unique", "num"], ["Range"], ["Examples"]]) {
    const th = el("th", cls, label);
    head.appendChild(th);
  }
  const body = table.createTBody();
  for (const c of ds.profile.columns) {
    const tr = body.insertRow();
    tr.insertCell().textContent = c.name;
    tr.insertCell().appendChild(el("span", "role", c.inferred_role));
    const missing = tr.insertCell();
    missing.className = "num";
    missing.textContent = c.null_count ? `${formatValue(c.null_count)} (${c.null_pct}%)` : "0";
    const unique = tr.insertCell();
    unique.className = "num";
    unique.textContent = formatValue(c.unique_count);
    const range = tr.insertCell();
    if (c.min !== null && c.min !== undefined) {
      const fmt = (v) => formatValue(v).replace(/ 00:00:00$/, "");
      range.textContent = `${fmt(c.min)} – ${fmt(c.max)}` + (c.mean != null ? ` (avg ${formatValue(c.mean)})` : "");
    } else {
      range.textContent = "—";
      range.className = "null";
    }
    const samples = tr.insertCell();
    samples.className = "wrap";
    samples.textContent = c.sample_values.join(", ");
  }
  $("dataset-dialog").showModal();
}

// ---- Upload ---------------------------------------------------------------

function setStatus(node, message, kind = "") {
  node.textContent = message;
  node.className = `status-line ${kind}`;
}

async function uploadFile(file) {
  const status = $("upload-status");
  const zone = $("dropzone");
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".csv")) {
    setStatus(status, "Please choose a .csv file.", "error");
    return;
  }
  zone.classList.add("busy");
  setStatus(status, `Uploading ${file.name}…`);
  const form = new FormData();
  form.append("file", file);
  try {
    const ds = await api("/datasets/upload", { method: "POST", body: form });
    setStatus(status, `Added ${ds.table_name}: ${formatValue(ds.row_count)} rows, ${ds.column_count} columns.`, "ok");
    await loadDatasets();
  } catch (e) {
    setStatus(status, e.message, "error");
  } finally {
    zone.classList.remove("busy");
    $("file-input").value = "";
  }
}

function setupUpload() {
  const zone = $("dropzone");
  $("file-input").addEventListener("change", (e) => uploadFile(e.target.files[0]));
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag");
    uploadFile(e.dataTransfer.files[0]);
  });
}

// ---- Ask ------------------------------------------------------------------

const resizeObserver = new ResizeObserver((entries) => {
  for (const entry of entries) entry.target._redraw?.();
});

function renderResult(card, result) {
  const { columns, rows } = result;
  const spec = chooseForm(columns, rows);
  const hasChart = spec.type !== "table";

  const head = el("div", "result-head");
  const title = el("span", "result-title", `Result · ${formatValue(rows.length)} row${rows.length === 1 ? "" : "s"}${result.truncated ? " (first 500)" : ""}`);
  head.appendChild(title);

  const view = el("div");
  const note = el("p", "note", hasChart ? chartNote(columns, rows, spec) : "");

  const showChart = () => {
    const chartBox = el("div");
    view.replaceChildren(chartBox);
    let lastWidth = 0;
    chartBox._redraw = () => {
      if (chartBox.clientWidth === lastWidth) return;
      lastWidth = chartBox.clientWidth;
      renderChart(chartBox, columns, rows, spec);
    };
    chartBox._redraw();
    resizeObserver.observe(chartBox);
    note.hidden = !note.textContent;
  };
  const showTable = () => {
    view.replaceChildren(renderTable(columns, rows));
    note.hidden = true;
  };

  if (hasChart) {
    const toggle = el("div", "segmented");
    toggle.setAttribute("role", "group");
    toggle.setAttribute("aria-label", "Result view");
    const chartBtn = el("button", null, "Chart");
    const tableBtn = el("button", null, "Table");
    for (const [btn, fn] of [[chartBtn, showChart], [tableBtn, showTable]]) {
      btn.type = "button";
      btn.addEventListener("click", () => {
        chartBtn.setAttribute("aria-pressed", String(btn === chartBtn));
        tableBtn.setAttribute("aria-pressed", String(btn === tableBtn));
        fn();
      });
    }
    chartBtn.setAttribute("aria-pressed", "true");
    tableBtn.setAttribute("aria-pressed", "false");
    toggle.append(chartBtn, tableBtn);
    head.appendChild(toggle);
  }

  card.append(head, view, note);
  hasChart ? showChart() : showTable();
}

function renderQueries(card, queries) {
  if (!queries.length) return;
  const details = el("details", "sql");
  const failed = queries.filter((q) => q.error).length;
  details.appendChild(
    el("summary", null, `Show SQL (${queries.length} quer${queries.length === 1 ? "y" : "ies"}${failed ? `, ${failed} retried after an error` : ""})`),
  );
  queries.forEach((q, i) => {
    const block = el("div", "query");
    block.appendChild(
      el("div", `query-label ${q.error ? "failed" : ""}`, q.error ? `Query ${i + 1} — failed: ${q.error}` : `Query ${i + 1}`),
    );
    block.appendChild(el("pre", null, q.sql));
    details.appendChild(block);
  });
  card.appendChild(details);
}

async function ask(question) {
  $("empty-state").hidden = true;
  const card = el("article", "answer pending");
  const q = el("p", "answer-question", "You asked: ");
  q.appendChild(el("strong", null, question));
  const text = el("p", "answer-text");
  text.append(el("span", "spinner"), document.createTextNode("Analyzing your data…"));
  card.append(q, text);
  $("answers").prepend(card);

  const button = $("ask-button");
  button.disabled = true;
  try {
    const ids = [...state.selected];
    const res = await api("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, dataset_ids: ids.length ? ids : null }),
    });
    card.classList.remove("pending");
    text.replaceChildren();
    richText(text, res.answer);
    if (res.result && res.result.rows.length) renderResult(card, res.result);
    renderQueries(card, res.queries);
  } catch (e) {
    card.classList.remove("pending");
    card.classList.add("error");
    text.textContent = e.message;
  } finally {
    button.disabled = false;
  }
}

function setupAsk() {
  const form = $("ask-form");
  const input = $("question");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (!question || $("ask-button").disabled) return;
    input.value = "";
    ask(question);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
}

// ---- Boot -----------------------------------------------------------------

$("dataset-dialog").addEventListener("click", (e) => {
  if (e.target.closest("[data-close]") || e.target === e.currentTarget) e.currentTarget.close();
});
setupUpload();
setupAsk();
loadHealth();
loadDatasets();
