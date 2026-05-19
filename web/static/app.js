const SECTION_COUNT = 112;

const endpoints = {
  resumen: "/api/dashboard/resumen",
  estado: "/api/estado",
  secciones: "/api/secciones/actual",
  horarios: "/api/horarios",
  ciclos: "/api/historial/ciclos",
  historialSecciones: "/api/historial/secciones",
};

const view = document.getElementById("view");
const apiStatus = document.getElementById("apiStatus");
const finsStatus = document.getElementById("finsStatus");
const freshnessStatus = document.getElementById("freshnessStatus");
const capabilityStatus = document.getElementById("capabilityStatus");
const rpiClock = document.getElementById("rpiClock");
const plcClock = document.getElementById("plcClock");
const uiClock = document.getElementById("uiClock");
const detailName = document.getElementById("detailName");
const detailType = document.getElementById("detailType");
const detailState = document.getElementById("detailState");
const detailTs = document.getElementById("detailTs");
const clearDetail = document.getElementById("clearDetail");

let activeView = "resumen";
let refreshTimer = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function sectionName(index) {
  return `Sec${String(index).padStart(3, "0")}`;
}

function setDetail(type, name, state, ts) {
  detailType.textContent = type || "-";
  detailName.textContent = name || "-";
  detailState.textContent = state || "-";
  detailTs.textContent = ts || "-";
}

function clearSelection() {
  document.querySelectorAll(".section-cell.selected").forEach((cell) => {
    cell.classList.remove("selected");
  });
}

clearDetail.addEventListener("click", () => {
  setDetail("-", "-", "-", "-");
  clearSelection();
});

async function fetchJson(path) {
  try {
    const response = await fetch(path, { headers: { Accept: "application/json" } });
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    if (!response.ok) {
      return { ok: false, status: response.status, data };
    }
    return { ok: true, status: response.status, data };
  } catch (error) {
    return { ok: false, status: 0, data: null, error };
  }
}

function asRows(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.rows)) return data.rows;
  if (Array.isArray(data?.historial)) return data.historial;
  if (Array.isArray(data?.ciclos)) return data.ciclos;
  if (data && typeof data === "object") return Object.values(data);
  return [];
}

function fieldValue(item, names) {
  for (const name of names) {
    if (item && item[name] !== undefined && item[name] !== null) return item[name];
  }
  return null;
}

function getTimestamp(item) {
  return item?.timestamp || item?.ts || item?.created_at || item?.fecha || "-";
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("es-ES", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function formatAge(seconds) {
  if (seconds === null || seconds === undefined) return "-";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function formatPlcClock(clock) {
  if (!clock) return "-";
  const year = Number(clock.anio) < 100 ? 2000 + Number(clock.anio) : Number(clock.anio);
  const parts = [clock.mes, clock.dia, clock.hora, clock.min, clock.seg];
  if ([year, ...parts].some((part) => Number.isNaN(Number(part)))) return "-";
  return `${year}-${pad2(clock.mes)}-${pad2(clock.dia)} ${pad2(clock.hora)}:${pad2(clock.min)}:${pad2(clock.seg)}`;
}

function pad2(value) {
  return String(value ?? 0).padStart(2, "0");
}

function badge(text, cls = "") {
  return `<span class="badge ${cls}">${escapeHtml(text)}</span>`;
}

function endpointState(result) {
  if (result.ok) return badge("OK", "ok");
  if (result.status === 404) return badge("SIN DATOS", "warn");
  if (result.status === 0) return badge("SIN CONEXION", "bad");
  return badge(`HTTP ${result.status}`, "bad");
}

function blockStatus(summary, block) {
  return summary?.bloques?.[block]?.status ?? null;
}

function blockError(summary, block) {
  return summary?.bloques?.[block]?.error ?? null;
}

function blockOk(summary, block) {
  return blockStatus(summary, block) === "ok";
}

function blockBadge(summary, block) {
  const status = blockStatus(summary, block);
  if (status === "ok") return badge("OK", "ok");
  if (status === "failed") return badge("FALLO", "bad");
  if (status === "absent") return badge("AUSENTE", "warn");
  return badge("SIN ESTADO", "warn");
}

function finsState(summary) {
  if (!summary) return { label: "PENDIENTE", cls: "warn" };
  const anyOk = ["secciones", "modo", "fotocelula", "reloj", "horarios", "diagnostico"]
    .some((block) => blockOk(summary, block));
  if (summary.fins_ok === true) return { label: "OK", cls: "ok" };
  if (anyOk) return { label: "PARCIAL", cls: "warn" };
  return { label: "FALLO", cls: "bad" };
}

function updateHeader(summaryResult) {
  uiClock.textContent = formatDateTime(new Date());
  if (!summaryResult.ok) {
    apiStatus.innerHTML = endpointState(summaryResult);
    finsStatus.innerHTML = badge("PENDIENTE", "warn");
    freshnessStatus.innerHTML = badge("SIN DATOS", "warn");
    capabilityStatus.innerHTML = badge("READ-ONLY", "neutral");
    rpiClock.textContent = "-";
    plcClock.textContent = "-";
    return;
  }

  const summary = summaryResult.data;
  const fins = finsState(summary);
  apiStatus.innerHTML = badge("OK", "ok");
  finsStatus.innerHTML = badge(fins.label, fins.cls);
  freshnessStatus.innerHTML = summary.frescura?.is_stale
    ? badge(`ANTIGUO ${formatAge(summary.frescura.age_seconds)}`, "warn")
    : badge(formatAge(summary.frescura?.age_seconds), "ok");
  capabilityStatus.innerHTML = summary.capabilities?.can_write
    ? badge("CONTROL", "warn")
    : badge("READ-ONLY", "neutral");
  rpiClock.textContent = formatDateTime(summary.timestamp_rpi);
  plcClock.textContent = formatPlcClock(summary.plc_reloj);
}

function renderPanel(title, sub, body, right = "") {
  return `
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>${escapeHtml(title)}</h2>
          <p class="sub">${escapeHtml(sub)}</p>
        </div>
        <div class="panel-action">${right}</div>
      </div>
      ${body}
    </section>
  `;
}

function renderEmpty(text) {
  return `<div class="empty">${escapeHtml(text)}</div>`;
}

function metric(label, value, hint = "") {
  return `
    <div class="metric">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${value}</div>
      ${hint ? `<div class="metric-hint">${escapeHtml(hint)}</div>` : ""}
    </div>
  `;
}

function renderKeyValues(values) {
  return values.map(([key, value]) => `
    <div class="kv">
      <span>${escapeHtml(key)}</span>
      <span>${value}</span>
    </div>
  `).join("");
}

function normalizeSections(data) {
  const source = data?.secciones ?? data?.items ?? data;
  const byKey = {};

  if (Array.isArray(source)) {
    source.forEach((item, idx) => {
      const id = fieldValue(item, ["seccion_id", "id", "numero", "seccion"]);
      byKey[String(id ?? idx + 1)] = item;
    });
  } else if (source && typeof source === "object") {
    Object.entries(source).forEach(([key, value]) => {
      byKey[key] = value;
    });
  }

  return Array.from({ length: SECTION_COUNT }, (_, idx) => {
    const index = idx + 1;
    const name = sectionName(index);
    const item = byKey[String(index)] || byKey[name] || null;
    return normalizeSection(index, name, item);
  });
}

function normalizeSection(index, name, item) {
  if (!item || typeof item !== "object") {
    return { index, name, state: "Sin datos", css: "state-unknown", ts: "-" };
  }

  const valid = fieldValue(item, ["valid", "valido", "is_valid"]);
  const finsOk = fieldValue(item, ["fins_ok", "lectura_ok"]);
  const absent = fieldValue(item, ["absent", "ausente"]);

  if (absent === true) {
    return { index, name, state: "Ausente", css: "state-unknown", ts: getTimestamp(item) };
  }
  if (valid === false) {
    return { index, name, state: "Invalido", css: "state-warn", ts: getTimestamp(item) };
  }
  if (finsOk === false) {
    return { index, name, state: "Fallo lectura", css: "state-bad", ts: getTimestamp(item) };
  }

  const explicitState = fieldValue(item, ["estado", "state", "estado_texto"]);
  if (explicitState !== null) {
    return { index, name, state: String(explicitState), css: "state-active", ts: getTimestamp(item) };
  }

  const auto = fieldValue(item, ["automatico", "auto"]);
  const manual = fieldValue(item, ["manual"]);
  const horario = fieldValue(item, ["horario_activo", "horario"]);
  const flags = [];
  if (auto === true) flags.push("Auto");
  if (manual === true) flags.push("Manual");
  if (horario === true) flags.push("Horario");

  return {
    index,
    name,
    state: flags.length ? flags.join(" + ") : "Apagada",
    css: flags.length ? "state-active" : "state-off",
    ts: getTimestamp(item),
  };
}

async function fetchSummary() {
  const result = await fetchJson(endpoints.resumen);
  updateHeader(result);
  return result;
}

async function showResumen() {
  const [summaryResult, seccionesResult, horariosResult] = await Promise.all([
    fetchSummary(),
    fetchJson(endpoints.secciones),
    fetchJson(endpoints.horarios),
  ]);

  if (!summaryResult.ok) {
    view.innerHTML = renderPanel(
      "Resumen",
      "No hay ciclo disponible todavia",
      renderEmpty("La API responde, pero aun no existe un ciclo persistido en SQLite."),
      endpointState(summaryResult),
    );
    return;
  }

  const summary = summaryResult.data;
  const counters = summary.secciones;
  const activeCount = Math.max(0, counters.con_dato - counters.apagadas);
  const horarioRows = asRows(horariosResult.data);
  const fins = finsState(summary);

  view.innerHTML =
    renderPanel("Estado operativo", "Lectura actual del sistema de alumbrado", `
      <div class="status-grid">
        ${metric("FINS", badge(fins.label, fins.cls), summary.fins_error || "Sin error global")}
        ${metric("Secciones activas", escapeHtml(String(activeCount)), `${counters.apagadas} apagadas / ${counters.con_dato} con dato`)}
        ${metric("Horarios raw", escapeHtml(String(horarioRows.length)), "Semantica PLC pendiente")}
        ${metric("Frescura", escapeHtml(formatAge(summary.frescura.age_seconds)), summary.frescura.is_stale ? "Dato antiguo" : "Dentro del umbral")}
      </div>
    `) +
    renderPanel("Bloques FINS", "Cada bloque puede estar OK aunque otro haya fallado", `
      ${renderKeyValues([
        ["Secciones", blockBadge(summary, "secciones")],
        ["Modo", blockBadge(summary, "modo")],
        ["Fotocelula", blockBadge(summary, "fotocelula")],
        ["Reloj PLC", blockBadge(summary, "reloj")],
        ["Horarios", blockBadge(summary, "horarios")],
        ["Diagnostico", blockBadge(summary, "diagnostico")],
      ])}
    `) +
    renderPanel("Modo actual", "Preparado para evolucion futura, bloqueado en esta fase", `
      <div class="readonly-box">
        <strong>Supervision read-only</strong>
        <span>No hay mandos, escrituras FINS ni cambios de horarios desde esta pantalla.</span>
      </div>
    `, badge(summary.capabilities.mode.toUpperCase(), "neutral")) +
    renderPanel("Contrato API", "Endpoints GET usados por el dashboard", `
      ${renderKeyValues([
        [endpoints.resumen, endpointState(summaryResult)],
        [endpoints.secciones, endpointState(seccionesResult)],
        [endpoints.horarios, endpointState(horariosResult)],
      ])}
    `);
}

async function showSecciones() {
  const [summaryResult, result] = await Promise.all([
    fetchSummary(),
    fetchJson(endpoints.secciones),
  ]);
  const rows = normalizeSections(result.data);
  const summary = summaryResult.data;
  const counterText = summaryResult.ok
    ? `${summary.secciones.con_dato}/${summary.secciones.total} con dato`
    : "Sin resumen";

  view.innerHTML = renderPanel(
    "Secciones",
    "112 secciones. Apagada significa fila valida con flags falsos.",
    result.ok
      ? `<div class="section-grid" id="sectionGrid"></div>`
      : renderEmpty("No hay bloque de secciones valido disponible."),
    `${endpointState(result)} ${badge(counterText, "neutral")}`,
  );

  if (!result.ok) return;

  const grid = document.getElementById("sectionGrid");
  rows.forEach((row) => {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = `section-cell ${row.css}`;
    cell.setAttribute("aria-label", `${row.name}: ${row.state}`);
    cell.innerHTML = `
      <div class="section-name">${escapeHtml(row.name)}</div>
      <div class="section-state">${escapeHtml(row.state)}</div>
    `;
    cell.addEventListener("click", () => {
      clearSelection();
      cell.classList.add("selected");
      setDetail("Seccion", row.name, row.state, formatDateTime(row.ts));
    });
    grid.appendChild(cell);
  });
}

async function showHorarios() {
  const [summaryResult, result] = await Promise.all([
    fetchSummary(),
    fetchJson(endpoints.horarios),
  ]);
  const rows = asRows(result.data);

  const body = rows.length
    ? `<div class="notice warn">
        Horarios mostrados como valores raw. No se interpreta semantica PLC hasta validar ladder.
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>Tramo</th><th>Inicio raw</th><th>Fin raw</th><th>Timestamp</th></tr></thead>
        <tbody>
          ${rows.map((row, index) => `
            <tr>
              <td class="mono">${escapeHtml(row?.tramo_id ?? row?.id ?? index + 1)}</td>
              <td class="mono">${escapeHtml(row?.inicio_raw ?? "-")}</td>
              <td class="mono">${escapeHtml(row?.fin_raw ?? "-")}</td>
              <td class="mono">${escapeHtml(formatDateTime(getTimestamp(row)))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table></div>`
    : renderEmpty("Sin horarios disponibles. Semantica D1000/D3632 pendiente.");

  const block = summaryResult.ok ? blockBadge(summaryResult.data, "horarios") : endpointState(result);
  view.innerHTML = renderPanel("Horarios", "Datos raw hasta confirmar semantica PLC", body, block);
}

async function showHistorial() {
  const [summaryResult, ciclos, secciones] = await Promise.all([
    fetchSummary(),
    fetchJson(endpoints.ciclos),
    fetchJson(endpoints.historialSecciones),
  ]);

  view.innerHTML =
    renderHistoryTable("Historial de ciclos", endpoints.ciclos, ciclos, renderCycleRow) +
    renderHistoryTable("Historial de secciones", endpoints.historialSecciones, secciones, renderSectionHistoryRow);
}

function renderHistoryTable(title, endpoint, result, rowRenderer) {
  const rows = asRows(result.data).slice(0, 50);
  const body = rows.length
    ? `<div class="table-wrap"><table>
        <thead><tr><th>#</th><th>Timestamp</th><th>Dato</th></tr></thead>
        <tbody>
          ${rows.map((row, index) => rowRenderer(row, index)).join("")}
        </tbody>
      </table></div>`
    : renderEmpty("Sin historial disponible.");

  return renderPanel(title, endpoint, body, endpointState(result));
}

function renderCycleRow(row, index) {
  const state = row?.fins_ok === true ? badge("OK", "ok") : badge("PARCIAL/FALLO", "warn");
  return `
    <tr>
      <td class="mono">${index + 1}</td>
      <td class="mono">${escapeHtml(formatDateTime(getTimestamp(row)))}</td>
      <td>${state} ${escapeHtml(row?.fins_error || "")}</td>
    </tr>
  `;
}

function renderSectionHistoryRow(row, index) {
  const section = normalizeSection(row?.seccion_id ?? index + 1, sectionName(row?.seccion_id ?? index + 1), row);
  return `
    <tr>
      <td class="mono">${escapeHtml(row?.seccion_id ?? index + 1)}</td>
      <td class="mono">${escapeHtml(formatDateTime(getTimestamp(row)))}</td>
      <td>${badge(section.state, section.css.replace("state-", ""))}</td>
    </tr>
  `;
}

async function showDiagnostico() {
  const checks = await Promise.all(Object.entries(endpoints).map(async ([name, path]) => {
    const result = await fetchJson(path);
    return [name, path, result];
  }));
  const summaryResult = checks.find(([name]) => name === "resumen")?.[2] ?? { ok: false };
  updateHeader(summaryResult);

  const summary = summaryResult.ok ? summaryResult.data : null;
  const blockRows = summary
    ? Object.entries(summary.bloques).map(([name, block]) => `
        <tr>
          <td>${escapeHtml(name)}</td>
          <td>${blockBadge(summary, name)}</td>
          <td>${escapeHtml(block.error || "-")}</td>
        </tr>
      `).join("")
    : "";

  const endpointRows = checks.map(([name, path, result]) => `
    <tr>
      <td>${escapeHtml(name)}</td>
      <td class="mono">${escapeHtml(path)}</td>
      <td>${endpointState(result)}</td>
    </tr>
  `).join("");

  view.innerHTML =
    renderPanel("Diagnostico FINS", "Estado por bloque de lectura", summary ? `
      <div class="table-wrap"><table>
        <thead><tr><th>Bloque</th><th>Estado</th><th>Error</th></tr></thead>
        <tbody>${blockRows}</tbody>
      </table></div>
    ` : renderEmpty("Sin resumen disponible.")) +
    renderPanel("Diagnostico API", "Comprobacion pasiva de endpoints read-only", `
      <div class="table-wrap"><table>
        <thead><tr><th>Recurso</th><th>Endpoint</th><th>Estado</th></tr></thead>
        <tbody>${endpointRows}</tbody>
      </table></div>
    `) +
    renderPanel("Preparacion modo autenticado", "Zona reservada para fase futura", `
      <div class="readonly-box locked">
        <strong>Control no disponible</strong>
        <span>La futura escritura requerira autenticacion, autorizacion, confirmacion y auditoria de servidor.</span>
      </div>
    `, badge("BLOQUEADO", "neutral"));
}

const views = {
  resumen: showResumen,
  secciones: showSecciones,
  horarios: showHorarios,
  historial: showHistorial,
  diagnostico: showDiagnostico,
};

async function renderActive() {
  clearTimeout(refreshTimer);
  view.setAttribute("aria-busy", "true");
  try {
    await views[activeView]();
  } finally {
    view.setAttribute("aria-busy", "false");
    refreshTimer = setTimeout(renderActive, activeView === "resumen" ? 5000 : 10000);
  }
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
    button.classList.add("active");
    activeView = button.dataset.view;
    renderActive();
  });
});

renderActive();
