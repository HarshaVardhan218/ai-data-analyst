// Small, dependency-free charts for agent results.
// Picks a form from the shape of the result, then draws it as SVG.
// All labels come from user data, so they are only ever set via textContent.

const NS = "http://www.w3.org/2000/svg";
const DATE_RE = /^\d{4}-\d{2}(-\d{2})?([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$/;
const MAX_BARS = 20;
const MAX_TABLE_ROWS = 200;

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

export function isNumber(v) {
  return typeof v === "number" && Number.isFinite(v);
}

export function formatValue(v) {
  if (v === null || v === undefined) return "—";
  if (isNumber(v)) return numberFormat.format(v);
  return String(v);
}

function formatTick(v) {
  const compact = Math.abs(v) >= 10000;
  return new Intl.NumberFormat(undefined, {
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 2,
  }).format(v);
}

function formatDateLabel(s) {
  // 2024-03-01T00:00:00 -> 2024-03-01; a first-of-month series reads better as 2024-03
  return String(s).replace(/T00:00:00(\.0+)?$/, "").replace(/[T ]00:00:00$/, "");
}

function svg(tag, attrs = {}, parent) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

function niceTicks(lo, hi, count = 5) {
  if (lo === hi) {
    hi = lo === 0 ? 1 : lo + Math.abs(lo) * 0.5;
    lo = Math.min(0, lo);
  }
  const rawStep = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(rawStep));
  const norm = rawStep / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const start = Math.floor(lo / step) * step;
  const end = Math.ceil(hi / step) * step;
  const ticks = [];
  for (let t = start; t <= end + step / 2; t += step) ticks.push(Math.round(t / step) * step);
  return ticks;
}

function truncate(text, maxChars) {
  const s = String(text);
  return s.length > maxChars ? s.slice(0, Math.max(1, maxChars - 1)) + "…" : s;
}

// ---- Form selection ------------------------------------------------------

/** Decide how to show a result: "stat", "bar", "line", or "table". */
export function chooseForm(columns, rows) {
  if (!rows.length || !columns.length) return { type: "table" };

  const numericCols = columns
    .map((_, i) => i)
    .filter((i) => rows.some((r) => isNumber(r[i])) && rows.every((r) => r[i] === null || isNumber(r[i])));
  if (!numericCols.length) return { type: "table" };

  if (rows.length === 1) {
    return { type: "stat", valueCols: numericCols.slice(0, 4) };
  }

  const labelCol = columns.findIndex((_, i) => !numericCols.includes(i));
  if (labelCol === -1) return { type: "table" };

  // Prefer a value column that isn't an identifier.
  const valueCol =
    numericCols.find((i) => !/(^id$|_id$)/i.test(columns[i])) ?? numericCols[0];
  const otherNumeric = numericCols.filter((i) => i !== valueCol);

  const labels = rows.map((r) => r[labelCol]);
  const isTime =
    rows.length >= 3 && labels.every((l) => l === null || (typeof l === "string" && DATE_RE.test(l)));

  if (isTime) return { type: "line", labelCol, valueCol, otherNumeric };
  if (rows.length <= 60) return { type: "bar", labelCol, valueCol, otherNumeric };
  return { type: "table" };
}

// ---- Tooltip -------------------------------------------------------------

function makeTooltip(container) {
  const tip = document.createElement("div");
  tip.className = "tooltip";
  tip.hidden = true;
  const value = document.createElement("div");
  value.className = "tt-value";
  const label = document.createElement("div");
  label.className = "tt-label";
  tip.append(value, label);
  container.appendChild(tip);
  return {
    show(x, y, valueText, labelText) {
      value.textContent = valueText;
      label.textContent = labelText;
      tip.hidden = false;
      const w = container.clientWidth;
      const half = tip.offsetWidth / 2;
      tip.style.left = `${Math.min(Math.max(x, half), w - half)}px`;
      tip.style.top = `${y}px`;
    },
    hide() {
      tip.hidden = true;
    },
  };
}

// ---- Bar chart (ranked horizontal bars, one hue) --------------------------

function drawBars(container, rows, spec, columns) {
  const data = rows.slice(0, MAX_BARS).map((r) => ({ label: r[spec.labelCol], value: r[spec.valueCol] }));
  const values = data.map((d) => d.value).filter(isNumber);
  const width = Math.max(container.clientWidth, 280);
  const labelW = Math.min(180, Math.round(width * 0.3));
  const valueRoom = 72;
  const rowH = 32;
  const barH = 20;
  const axisH = 26;
  const plotW = Math.max(width - labelW - valueRoom, 60);
  const height = data.length * rowH + axisH;

  const ticks = niceTicks(Math.min(0, ...values), Math.max(0, ...values), width < 480 ? 3 : 5);
  const d0 = ticks[0];
  const d1 = ticks[ticks.length - 1];
  const x = (v) => labelW + ((v - d0) / (d1 - d0)) * plotW;

  const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, height, role: "img" });
  root.setAttribute("aria-label", `Bar chart of ${columns[spec.valueCol]} by ${columns[spec.labelCol]}`);

  const plotBottom = data.length * rowH;
  for (const t of ticks) {
    svg("line", { class: "gridline", x1: x(t), x2: x(t), y1: 0, y2: plotBottom }, root);
    const tick = svg("text", { class: "tick", x: x(t), y: plotBottom + 18, "text-anchor": "middle" }, root);
    tick.textContent = formatTick(t);
  }

  const tooltip = makeTooltip(container);
  const maxChars = Math.max(4, Math.floor((labelW - 14) / 7));

  data.forEach((d, i) => {
    const g = svg("g", { class: "row" }, root);
    const y = i * rowH + (rowH - barH) / 2;
    const cy = i * rowH + rowH / 2;

    const name = svg("text", { class: "cat-label", x: labelW - 10, y: cy + 4.5, "text-anchor": "end" }, g);
    name.textContent = truncate(formatValue(d.label), maxChars);

    let tipX = x(0);
    if (isNumber(d.value)) {
      const x0 = x(0);
      const x1 = x(d.value);
      const w = Math.abs(x1 - x0);
      if (w > 0) {
        const r = Math.min(4, w / 2);
        // Rounded at the data end, square at the baseline.
        const path =
          d.value >= 0
            ? `M${x0},${y} H${x1 - r} Q${x1},${y} ${x1},${y + r} V${y + barH - r} Q${x1},${y + barH} ${x1 - r},${y + barH} H${x0} Z`
            : `M${x0},${y} H${x1 + r} Q${x1},${y} ${x1},${y + r} V${y + barH - r} Q${x1},${y + barH} ${x1 + r},${y + barH} H${x0} Z`;
        svg("path", { class: "bar", d: path }, g);
      }
      const label = svg(
        "text",
        {
          class: "value-label",
          x: d.value >= 0 ? x1 + 6 : x1 - 6,
          y: cy + 4.5,
          "text-anchor": d.value >= 0 ? "start" : "end",
        },
        g,
      );
      label.textContent = formatValue(d.value);
      tipX = x1;
    } else {
      const label = svg("text", { class: "tick", x: x(0) + 6, y: cy + 4.5 }, g);
      label.textContent = "no value";
    }

    const hit = svg("rect", { class: "bar-hit", x: 0, y: i * rowH, width, height: rowH, tabindex: 0 }, g);
    hit.setAttribute("aria-label", `${formatValue(d.label)}: ${formatValue(d.value)}`);
    const show = () => tooltip.show(tipX, y, formatValue(d.value), `${formatValue(d.label)} · ${columns[spec.valueCol]}`);
    hit.addEventListener("pointerenter", show);
    hit.addEventListener("focus", show);
    hit.addEventListener("pointerleave", () => tooltip.hide());
    hit.addEventListener("blur", () => tooltip.hide());
  });

  svg("line", { class: "baseline", x1: x(0), x2: x(0), y1: 0, y2: plotBottom }, root);
  container.prepend(root);
}

// ---- Line chart (one series over time) ------------------------------------

function drawLine(container, rows, spec, columns) {
  const data = rows
    .map((r) => ({ label: r[spec.labelCol], value: r[spec.valueCol] }))
    .filter((d) => d.label !== null)
    .sort((a, b) => (a.label < b.label ? -1 : a.label > b.label ? 1 : 0));
  const values = data.map((d) => d.value).filter(isNumber);
  const width = Math.max(container.clientWidth, 280);
  const left = 52;
  const right = 72;
  const top = 12;
  const plotH = 240;
  const axisH = 28;
  const height = top + plotH + axisH;
  const plotW = width - left - right;

  const ticks = niceTicks(Math.min(0, ...values), Math.max(0, ...values), 4);
  const d0 = ticks[0];
  const d1 = ticks[ticks.length - 1];
  const x = (i) => left + (data.length === 1 ? plotW / 2 : (i / (data.length - 1)) * plotW);
  const y = (v) => top + plotH - ((v - d0) / (d1 - d0)) * plotH;

  const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, height, role: "img" });
  root.setAttribute("aria-label", `Line chart of ${columns[spec.valueCol]} over ${columns[spec.labelCol]}`);

  for (const t of ticks) {
    svg("line", { class: t === 0 ? "baseline" : "gridline", x1: left, x2: left + plotW, y1: y(t), y2: y(t) }, root);
    const tick = svg("text", { class: "tick", x: left - 8, y: y(t) + 4, "text-anchor": "end" }, root);
    tick.textContent = formatTick(t);
  }

  const maxXLabels = Math.max(2, Math.floor(plotW / 90));
  const every = Math.ceil(data.length / maxXLabels);
  data.forEach((d, i) => {
    if (i % every !== 0 && i !== data.length - 1) return;
    if (i !== data.length - 1 && data.length - 1 - i < every) return; // keep the last label clear
    const t = svg("text", { class: "tick", x: x(i), y: top + plotH + 20, "text-anchor": "middle" }, root);
    t.textContent = formatDateLabel(d.label);
  });

  // Draw contiguous runs, breaking the line where values are missing.
  let run = [];
  const runs = [];
  data.forEach((d, i) => {
    if (isNumber(d.value)) run.push([x(i), y(d.value)]);
    else if (run.length) {
      runs.push(run);
      run = [];
    }
  });
  if (run.length) runs.push(run);
  for (const pts of runs) {
    const line = pts.map(([px, py], j) => `${j ? "L" : "M"}${px},${py}`).join(" ");
    if (pts.length > 1) {
      const base = y(Math.max(d0, 0));
      svg("path", { class: "area", d: `${line} L${pts[pts.length - 1][0]},${base} L${pts[0][0]},${base} Z` }, root);
    }
    svg("path", { class: "line", d: line }, root);
  }

  // End dot + value label on the latest point.
  const lastIdx = data.map((d) => isNumber(d.value)).lastIndexOf(true);
  if (lastIdx >= 0) {
    svg("circle", { class: "dot", cx: x(lastIdx), cy: y(data[lastIdx].value), r: 4 }, root);
    const end = svg("text", { class: "value-label", x: x(lastIdx) + 10, y: y(data[lastIdx].value) + 4 }, root);
    end.textContent = formatValue(data[lastIdx].value);
  }

  // Crosshair that snaps to the nearest point; works with mouse and arrow keys.
  const cross = svg("line", { class: "crosshair", y1: top, y2: top + plotH, visibility: "hidden" }, root);
  const hoverDot = svg("circle", { class: "dot", r: 4, visibility: "hidden" }, root);
  const overlay = svg("rect", { x: left, y: top, width: plotW, height: plotH, fill: "transparent", tabindex: 0 }, root);
  overlay.setAttribute("aria-label", "Use left and right arrow keys to read values");
  const tooltip = makeTooltip(container);
  let current = -1;

  const showIndex = (i) => {
    current = Math.max(0, Math.min(data.length - 1, i));
    const d = data[current];
    const px = x(current);
    cross.setAttribute("x1", px);
    cross.setAttribute("x2", px);
    cross.setAttribute("visibility", "visible");
    if (isNumber(d.value)) {
      hoverDot.setAttribute("cx", px);
      hoverDot.setAttribute("cy", y(d.value));
      hoverDot.setAttribute("visibility", "visible");
    } else {
      hoverDot.setAttribute("visibility", "hidden");
    }
    const ty = isNumber(d.value) ? y(d.value) : top + plotH / 2;
    tooltip.show(px * (container.clientWidth / width), ty * (container.clientWidth / width), formatValue(d.value), formatDateLabel(d.label));
  };
  const hide = () => {
    cross.setAttribute("visibility", "hidden");
    hoverDot.setAttribute("visibility", "hidden");
    tooltip.hide();
  };

  overlay.addEventListener("pointermove", (e) => {
    const box = root.getBoundingClientRect();
    const sx = ((e.clientX - box.left) / box.width) * width;
    const i = data.length === 1 ? 0 : Math.round(((sx - left) / plotW) * (data.length - 1));
    showIndex(i);
  });
  overlay.addEventListener("pointerleave", hide);
  overlay.addEventListener("blur", hide);
  overlay.addEventListener("focus", () => showIndex(current < 0 ? data.length - 1 : current));
  overlay.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { showIndex(current - 1); e.preventDefault(); }
    if (e.key === "ArrowRight") { showIndex(current + 1); e.preventDefault(); }
  });

  container.prepend(root);
}

// ---- Stat tiles (single-row results) -------------------------------------

function drawStats(container, rows, spec, columns) {
  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.flexWrap = "wrap";
  wrap.style.gap = "16px 40px";
  for (const i of spec.valueCols) {
    const tile = document.createElement("div");
    tile.className = "stat";
    const label = document.createElement("span");
    label.className = "stat-label";
    label.textContent = columns[i].replace(/_/g, " ");
    const value = document.createElement("span");
    value.className = "stat-value";
    value.textContent = formatValue(rows[0][i]);
    tile.append(label, value);
    wrap.appendChild(tile);
  }
  container.appendChild(wrap);
}

/** Render a chart into `container` (cleared first). Re-call on resize. */
export function renderChart(container, columns, rows, spec) {
  container.replaceChildren();
  container.classList.add("chart");
  if (spec.type === "bar") drawBars(container, rows, spec, columns);
  else if (spec.type === "line") drawLine(container, rows, spec, columns);
  else if (spec.type === "stat") drawStats(container, rows, spec, columns);
}

export function chartNote(columns, rows, spec) {
  const notes = [];
  if (spec.type === "bar" && rows.length > MAX_BARS) notes.push(`Showing the first ${MAX_BARS} of ${rows.length} rows.`);
  if ((spec.type === "bar" || spec.type === "line") && spec.otherNumeric.length) {
    const others = spec.otherNumeric.map((i) => columns[i]).join(", ");
    notes.push(`Chart shows ${columns[spec.valueCol]}; ${others} ${spec.otherNumeric.length > 1 ? "are" : "is"} in the table.`);
  }
  return notes.join(" ");
}

// ---- Table ---------------------------------------------------------------

export function renderTable(columns, rows) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const table = document.createElement("table");
  table.className = "data-table";
  const numeric = columns.map((_, i) => rows.some((r) => isNumber(r[i])) && rows.every((r) => r[i] === null || isNumber(r[i])));

  const head = table.createTHead().insertRow();
  columns.forEach((c, i) => {
    const th = document.createElement("th");
    th.textContent = c;
    if (numeric[i]) th.className = "num";
    head.appendChild(th);
  });
  const body = table.createTBody();
  for (const r of rows.slice(0, MAX_TABLE_ROWS)) {
    const tr = body.insertRow();
    r.forEach((v, i) => {
      const td = tr.insertCell();
      td.textContent = formatValue(v);
      if (v === null) td.className = "null";
      else if (numeric[i]) td.className = "num";
    });
  }
  wrap.appendChild(table);
  return wrap;
}
