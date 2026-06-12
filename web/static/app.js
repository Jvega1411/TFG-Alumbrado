// --- CONSTANTS ------------------------------------------------------------
const SECTION_COUNT = 112;

const endpoints = {
  resumen: "/api/dashboard/resumen",
  estado: "/api/estado",
  secciones: "/api/secciones/actual",
  horarios: "/api/horarios",
  ciclos: "/api/historial/ciclos",
  historialSecciones: "/api/historial/secciones",
  historialHorarios: "/api/historial/horarios",
  cicloVector: (id) => `/api/ciclos/${id}/vector_salidas_logicas`,
  cicloContextoRaw: (id) => `/api/ciclos/${id}/contexto_plc_raw`,
};

const DIAGNOSTIC_ENDPOINTS = ["resumen", "estado", "secciones", "horarios"];

// SVG icons — consistentes entre OS/fuentes a diferencia de caracteres Unicode
const ICON_CHECK = `<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="1.5 5 4 7.5 8.5 2"/></svg>`;
const ICON_CROSS = `<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><line x1="2" y1="2" x2="8" y2="8"/><line x1="8" y1="2" x2="2" y2="8"/></svg>`;
const ICON_WARN = `<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M5 2v3.5"/><circle cx="5" cy="8" r="0.75" fill="currentColor" stroke="none"/></svg>`;

const SKELETON = `<div class="skeleton-panel"></div><div class="skeleton-panel"></div><div class="skeleton-panel"></div>`;

const STALE_WARN_FALLBACK_S = 3600;
const STALE_CRIT_S = 86400;  // 24h → aviso rojo
const REFRESH_INTERVALS = { estado: 3000, secciones: 5000 };

function staleWarnSeconds(summary) {
  const value = Number(summary?.frescura?.stale_after_seconds);
  return Number.isFinite(value) && value > 0 ? value : STALE_WARN_FALLBACK_S;
}

function isStaleWarning(summary) {
  const age = summary?.frescura?.age_seconds;
  return age !== null && age !== undefined && age >= staleWarnSeconds(summary);
}

// --- STATE ----------------------------------------------------------------
let activeView = "estado";
let currentViewRendered = null;
let refreshTimer = null;
let historySelectedCicloId = null;
let historyLoadedCiclos = [];
let historyHasMore = false;
let historyAnchorTs = null;
let historySelectedSecciones = null;
let sectionFilterState = "all";
let sectionSearchTerm = "";
let sectionSearchTimer = null;
let diagnosticoOpen = false;
let diagnosticoChecks = null;
let diagnosticoChecksPromise = null;

// --- UTILITIES ------------------------------------------------------------
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
  if (detailHeading) {
    detailHeading.textContent = activeView === "historial" ? "Ciclo"
      : activeView === "secciones" ? "Cercha"
      : "Detalle";
  }
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

// --- API ------------------------------------------------------------------
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

async function fetchSummary() {
  return fetchJson(endpoints.resumen);
}

async function fetchEndpointChecks() {
  const checks = await Promise.all(
    DIAGNOSTIC_ENDPOINTS.map(async (name) => {
      const result = await fetchJson(endpoints[name]);
      return [name, endpoints[name], result];
    }),
  );
  const estado = checks.find(([name]) => name === "estado")?.[2];
  const cicloId = estado?.ok ? estado.data?.id : null;
  if (!cicloId) return checks;
  const detailChecks = await Promise.all([
    ["vector_salidas_logicas", endpoints.cicloVector(cicloId)],
    ["contexto_plc_raw", endpoints.cicloContextoRaw(cicloId)],
  ].map(async ([name, path]) => [name, path, await fetchJson(path)]));
  return checks.concat(detailChecks);
}

// --- RENDER HELPERS -------------------------------------------------------
function asRows(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.rows)) return data.rows;
  if (Array.isArray(data?.historial)) return data.historial;
  if (Array.isArray(data?.ciclos)) return data.ciclos;
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

function formatSpainDateTime(value) {
  if (!value) return "-";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const formatted = new Intl.DateTimeFormat("es-ES", {
    timeZone: "Europe/Madrid",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
  const offset = new Intl.DateTimeFormat("en-US", {
    timeZone: "Europe/Madrid",
    timeZoneName: "shortOffset",
    hour: "2-digit",
  }).formatToParts(date).find((part) => part.type === "timeZoneName")?.value.replace("GMT", "UTC");
  return offset ? `${formatted} (${offset})` : formatted;
}

function formatAge(seconds) {
  if (seconds === null || seconds === undefined) return "-";
  if (seconds < 0) return "TS futuro";
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

function miniBadge(ok, absent = false) {
  if (absent || ok === null || ok === undefined) {
    return `<span class="mini-badge neutral" title="Sin estado" aria-label="Sin estado">?</span>`;
  }
  if (ok === true || ok === "ok") {
    return `<span class="mini-badge ok" title="OK" aria-label="OK">${ICON_CHECK}</span>`;
  }
  return `<span class="mini-badge bad" title="Fallo" aria-label="Fallo">${ICON_CROSS}</span>`;
}

function statusMiniBadge(statusField) {
  if (statusField === null || statusField === undefined) return miniBadge(null, true);
  if (statusField === "absent") {
    return `<span class="mini-badge warn" title="Ausente" aria-label="Ausente">${ICON_WARN}</span>`;
  }
  return miniBadge(statusField === "ok");
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

// --- DOMAIN ---------------------------------------------------------------
function sectionClass(row) {
  if (row.css === "state-active") return "active";
  if (row.css === "state-off") return "off";
  if (row.css === "state-bad") return "bad";
  if (row.css === "state-warn") return "warn";
  return "unknown";
}

function sectionCounts(rows) {
  return rows.reduce((acc, row) => {
    acc.total += 1;
    acc[sectionClass(row)] += 1;
    return acc;
  }, { total: 0, active: 0, off: 0, bad: 0, warn: 0, unknown: 0 });
}

function anomalyItems(summary, seccionesResult, horariosResult) {
  const items = [];
  const age = summary?.frescura?.age_seconds;
  if (age !== null && age !== undefined && age >= STALE_CRIT_S) {
    items.push(["Pipeline caido", `Sin datos desde hace ${formatAge(age)}. Revisar publisher en RPi.`]);
  } else if (isStaleWarning(summary)) {
    items.push(["Dato antiguo", `Ultima lectura RPi hace ${formatAge(age)}. Pipeline posiblemente detenido.`]);
  }
  if (age !== null && age !== undefined && age < 0) {
    items.push(["Timestamp futuro", "La marca temporal RPi esta por delante del reloj de la UI."]);
  }
  const fins = finsState(summary);
  if (fins.label !== "OK") {
    items.push([`FINS ${fins.label}`, summary?.fins_error || "Uno o mas bloques FINS no estan en estado OK."]);
  }
  if (summary?.diagnostico?.cycle_time_error) items.push(["PLC cycle time", "El diagnostico PLC marca error de tiempo de ciclo."]);
  if (summary?.diagnostico?.low_battery) items.push(["Bateria PLC", "El diagnostico PLC marca bateria baja."]);
  if (summary?.diagnostico?.io_verify_error) items.push(["I/O verify", "El diagnostico PLC marca error de verificacion I/O."]);
  if (summary?.secciones && summary.secciones.con_dato < summary.secciones.total) {
    items.push(["Secciones sin dato", `${summary.secciones.total - summary.secciones.con_dato} secciones no tienen lectura valida.`]);
  }
  Object.entries(summary?.bloques ?? {}).forEach(([name, block]) => {
    if (block.status === "failed") items.push([`Bloque ${name}`, block.error || "Fallo de lectura."]);
    if (block.status === "absent") items.push([`Bloque ${name}`, "Bloque ausente en el ciclo."]);
  });
  if (!seccionesResult.ok) items.push(["Endpoint secciones", `No disponible (${seccionesResult.status || "sin conexion"}).`]);
  if (!horariosResult.ok && horariosResult.status !== 404) items.push(["Endpoint horarios", `No disponible (${horariosResult.status || "sin conexion"}).`]);
  return items;
}

function finsState(summary) {
  if (!summary) return { label: "PENDIENTE", cls: "warn" };
  const anyOk = ["secciones", "modo", "fotocelula", "reloj", "horarios", "diagnostico",
    "reset_temporizado", "hmi_original", "reloj_ar", "vector_salidas_logicas",
    "contexto_plc_raw"]
    .some((block) => blockOk(summary, block));
  if (summary.fins_ok === true) return { label: "OK", cls: "ok" };
  if (anyOk) return { label: "PARCIAL", cls: "warn" };
  return { label: "FALLO", cls: "bad" };
}

function renderPanel(title, body, right = "") {
  return `
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>${escapeHtml(title)}</h2>
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

  const observed = fieldValue(item, ["senal_observada_activa"]);
  const auto = fieldValue(item, ["automatico_calculado"]);
  const manual = fieldValue(item, ["manual_activo"]);
  const horario = fieldValue(item, ["salida_interna"]);
  const explicitState = fieldValue(item, ["estado_observable", "estado", "state", "estado_texto"]);
  const flags = [];
  if (auto === true) flags.push("Auto calc. obs.");
  if (manual === true) flags.push("Orden manual obs.");
  if (horario === true) flags.push("Interna volatil obs.");

  const observedActive = typeof observed === "boolean" ? observed : flags.length > 0;
  const defaultState = observedActive ? flags.join(" + ") : "Sin senal observada";
  const explicitText = explicitState !== null ? String(explicitState) : "";
  const state = flags.length ? defaultState : (explicitText || defaultState);

  return {
    index,
    name,
    state,
    css: observedActive ? "state-active" : "state-off",
    ts: getTimestamp(item),
  };
}

// --- VIEWS ----------------------------------------------------------------
function renderDiagnosticoBody(summary, checks) {
  const blockRows = Object.entries(summary?.bloques ?? {}).map(([name, block]) => `
        <tr>
          <td>${escapeHtml(name)}</td>
          <td>${blockBadge(summary, name)}</td>
          <td>${escapeHtml(block?.error || "-")}</td>
        </tr>
      `).join("");

  const endpointRows = checks.map(([name, path, result]) => `
    <tr>
      <td>${escapeHtml(name)}</td>
      <td class="mono">${escapeHtml(path)}</td>
      <td>${endpointState(result)}</td>
    </tr>
  `).join("");

  return `
    ${summary && blockRows
      ? `<div class="table-wrap"><table>
           <thead><tr><th>Bloque</th><th>Estado</th><th>Error</th></tr></thead>
           <tbody>${blockRows}</tbody>
         </table></div>`
      : renderEmpty("Sin resumen disponible.")}
    <div class="table-wrap diag-endpoints"><table>
      <thead><tr><th>Recurso</th><th>Endpoint</th><th>Estado</th></tr></thead>
      <tbody>${endpointRows}</tbody>
    </table></div>
  `;
}

function renderDiagnosticoSection(summary) {
  const body = diagnosticoChecks
    ? renderDiagnosticoBody(summary, diagnosticoChecks)
    : `<p class="empty">Cargando...</p>`;
  return `<details class="panel" data-diagnostico${diagnosticoOpen ? " open" : ""}>
    <summary class="diag-summary">Diagnóstico</summary>
    <div class="diag-body">${body}</div>
  </details>`;
}

async function showResumen() {
  const [summaryResult, seccionesResult, horariosResult] = await Promise.all([
    fetchSummary(),
    fetchJson(endpoints.secciones),
    fetchJson(endpoints.horarios),
  ]);

  if (!summaryResult.ok) {
    view.innerHTML = renderPanel(
      "Estado",
      renderEmpty("La API responde, pero aun no existe un ciclo persistido en SQLite."),
      endpointState(summaryResult),
    );
    return;
  }

  const summary = summaryResult.data;
  const counters = summary.secciones;
  const activeCount = counters.senales_observadas_activas
    ?? Math.max(0, counters.con_dato - (counters.sin_senal_observada ?? 0));
  const noSignalCount = counters.sin_senal_observada ?? Math.max(0, counters.con_dato - activeCount);
  const sectionRows = seccionesResult.ok ? normalizeSections(seccionesResult.data) : [];
  const counts = sectionCounts(sectionRows);
  const fins = finsState(summary);
  const age = summary.frescura.age_seconds;
  const staleWarn = staleWarnSeconds(summary);
  const freshnessHint = age < 0 ? "Timestamp RPi en futuro"
    : age >= STALE_CRIT_S ? "Sin datos en mas de 24h"
    : isStaleWarning(summary) ? `Dato antiguo (mas de ${formatAge(staleWarn)})`
    : "Dentro del umbral";
  const freshnessHtml = age !== null && age !== undefined && age < 0 ? badge("TS FUTURO", "bad")
    : age >= STALE_CRIT_S ? badge(`CAIDO ${formatAge(age)}`, "bad")
    : isStaleWarning(summary) ? badge(`ANTIGUO ${formatAge(age)}`, "warn")
    : badge(formatAge(age), "ok");
  const anomalies = anomalyItems(summary, seccionesResult, horariosResult);
  const isCritical = age !== null && age !== undefined && (age < 0 || age >= STALE_CRIT_S);
  const healthClass = isCritical ? "bad" : (anomalies.length ? "warn" : "ok");
  const healthLabel = anomalies.length ? `${anomalies.length} avisos` : "Sin avisos";

  view.innerHTML =
    renderPanel("Estado", `
      <div class="ops-hero ${healthClass}">
        <div class="ops-primary">
          <span>Estado de datos</span>
          <strong>${escapeHtml(healthLabel)}</strong>
          <small>${escapeHtml(freshnessHint)}</small>
        </div>
        <div class="ops-kpis">
          ${metric("FINS", badge(fins.label, fins.cls), summary.fins_error || "Sin error global")}
          ${metric("Frescura", escapeHtml(formatAge(age)), freshnessHint)}
          ${metric("Secciones con senal", escapeHtml(String(activeCount)), `${noSignalCount} sin senal observada`)}
        </div>
      </div>
      <div class="sys-status-row merged">
        ${badge("API OK", "ok")}
        ${badge(`FINS ${fins.label}`, fins.cls)}
        ${freshnessHtml}
      </div>
      <div class="sys-clocks merged">
        <div><span>RPi</span><strong>${escapeHtml(formatDateTime(summary.timestamp_rpi))}</strong></div>
        <div><span>PLC</span><strong>${escapeHtml(formatPlcClock(summary.plc_reloj))}</strong></div>
        <div><span>UI</span><strong>${escapeHtml(formatDateTime(new Date()))}</strong></div>
      </div>
      <div class="sys-blocks">
        ${renderKeyValues([
          ["Secciones", blockBadge(summary, "secciones")],
          ["Modo", blockBadge(summary, "modo")],
          ["Fotocelula", blockBadge(summary, "fotocelula")],
          ["Reloj PLC", blockBadge(summary, "reloj")],
          ["Horarios", blockBadge(summary, "horarios")],
          ["Diagnostico", blockBadge(summary, "diagnostico")],
          ["HMI", blockBadge(summary, "hmi_original")],
          ["Vector logico", blockBadge(summary, "vector_salidas_logicas")],
          ["Contexto raw", blockBadge(summary, "contexto_plc_raw")],
        ])}
      </div>
    `) +
    renderPanel("Avisos", anomalies.length
      ? `<div class="alert-list">${anomalies.map(([title, text]) => `
          <div class="alert-item">
            <strong>${escapeHtml(title)}</strong>
            <span>${escapeHtml(text)}</span>
          </div>
        `).join("")}</div>`
      : `<div class="empty success">No hay anomalias operativas en la ultima lectura.</div>`) +
    renderPanel("Secciones", `
      <div class="section-summary">
        ${metric("Senal obs.", escapeHtml(String(counts.active)), "Auto calculada, orden manual o interna volatil")}
        ${metric("Sin senal", escapeHtml(String(counts.off)), "Fila valida con flags observados falsos")}
        ${metric("Fallos", escapeHtml(String(counts.bad)), "Lectura invalida FINS")}
        ${metric("Sin datos", escapeHtml(String(counts.unknown)), "Ausente o no disponible")}
      </div>
      <div class="console-actions">
        <button type="button" class="secondary-action" data-jump="secciones">Abrir secciones</button>
        <button type="button" class="secondary-action" data-jump="historial">Ver historial</button>
        <button type="button" class="secondary-action" data-open-diagnostico>Diagnóstico</button>
      </div>
    `, `${endpointState(seccionesResult)} ${badge(`${counters.con_dato}/${counters.total} con dato`, "neutral")}`) +
    renderDiagnosticoSection(summary);
}

async function showSecciones() {
  if (!["all", "active", "off"].includes(sectionFilterState)) {
    sectionFilterState = "all";
  }
  const [summaryResult, result] = await Promise.all([
    fetchSummary(),
    fetchJson(endpoints.secciones),
  ]);
  const rows = normalizeSections(result.data);
  const counts = sectionCounts(rows);
  const search = sectionSearchTerm.trim().toLowerCase();
  const filteredRows = rows.filter((row) => {
    const rowClass = sectionClass(row);
    const matchesFilter = sectionFilterState === "all" || rowClass === sectionFilterState;
    const matchesSearch = !search || row.name.toLowerCase().includes(search) || String(row.index).includes(search);
    return matchesFilter && matchesSearch;
  });

  view.innerHTML = renderPanel(
    "Secciones",
    result.ok
      ? `<div class="section-tools">
          <div class="filter-group" aria-label="Filtro de secciones">
            ${[
              ["all", `Todas ${counts.total}`],
              ["active", `Con senal ${counts.active}`],
              ["off", `Sin senal ${counts.off}`],
            ].map(([value, label]) => `
              <button type="button" class="filter-chip${sectionFilterState === value ? " active" : ""}" data-section-filter="${value}">
                ${escapeHtml(label)}
              </button>
            `).join("")}
          </div>
          <label class="section-search">
            <span>Buscar</span>
            <input id="sectionSearch" type="search" value="${escapeHtml(sectionSearchTerm)}" placeholder="Sec001 o 1">
          </label>
        </div>
        <div class="section-grid" id="sectionGrid"></div>`
      : renderEmpty("No hay bloque de secciones valido disponible."),
  );

  if (!result.ok) return;

  const grid = document.getElementById("sectionGrid");
  if (!filteredRows.length) {
    grid.innerHTML = `<div class="empty full-row">No hay secciones para el filtro actual.</div>`;
  }
  filteredRows.forEach((row) => {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = `section-cell ${row.css}`;
    cell.setAttribute("aria-label", `${row.name}: ${row.state}`);
    cell.dataset.secName = row.name;
    cell.dataset.secState = row.state;
    cell.dataset.secTs = formatDateTime(row.ts);
    cell.innerHTML = `
      <div class="section-name">${escapeHtml(row.name)}</div>
      <div class="section-state">${escapeHtml(row.state)}</div>
    `;
    grid.appendChild(cell);
  });
}

function bitBadge(val) {
  if (val === null || val === undefined) return badge("?", "warn");
  return val ? badge("TRUE obs.", "ok") : badge("FALSE obs.", "off");
}

function renderCicloDetail(ciclo, secciones) {
  if (!ciclo) return "";

  const ts = formatSpainDateTime(ciclo.timestamp);
  const plcClockObj = {
    seg: ciclo.plc_seg,
    min: ciclo.plc_min,
    hora: ciclo.plc_hora,
    dia: ciclo.plc_dia,
    mes: ciclo.plc_mes,
    anio: ciclo.plc_anio,
  };

  const metaBlock = `
    <div class="ciclo-meta">
      <div class="ciclo-meta-item">
        <span class="ciclo-meta-label">Reloj PLC</span>
        <strong class="ciclo-meta-val">${escapeHtml(formatPlcClock(plcClockObj))}</strong>
      </div>
      <div class="ciclo-meta-item">
        <span class="ciclo-meta-label">Fotocelula</span>
        <div class="ciclo-foto-row">
          <span>Entrada ${bitBadge(ciclo.fotocelula_entrada)}</span>
          <span>Mem.fun ${bitBadge(ciclo.fotocelula_mem_fun)}</span>
          <span>Mem.act ${bitBadge(ciclo.fotocelula_mem_act)}</span>
        </div>
      </div>
    </div>
  `;

  if (secciones === null) {
    return renderPanel(
      ts,
      `<p class="sub">Ciclo #${escapeHtml(ciclo.id)}</p>` + metaBlock + renderEmpty("Cargando cerchas..."),
    );
  }

  if (!Array.isArray(secciones) || secciones.length === 0) {
    const msg = ciclo.secciones_status === "failed" ? "Lectura de cerchas fallida en este ciclo."
      : ciclo.secciones_status === "absent" ? "Bloque de cerchas ausente en este ciclo."
      : "Sin datos de cerchas para este ciclo.";
    return renderPanel(
      ts,
      `<p class="sub">Ciclo #${escapeHtml(ciclo.id)}</p>` + metaBlock + renderEmpty(msg),
    );
  }

  const rows = normalizeSections(secciones);
  const activeCount = rows.filter((r) => r.css === "state-active").length;
  const gridHtml = rows.map((row) => `
    <button type="button" class="section-cell ${row.css}"
            data-sec-name="${escapeHtml(row.name)}"
            data-sec-state="${escapeHtml(row.state)}"
            data-sec-ts="${escapeHtml(formatDateTime(row.ts))}"
            aria-label="${escapeHtml(row.name)}: ${escapeHtml(row.state)}">
      <div class="section-name">${escapeHtml(row.name)}</div>
      <div class="section-state">${escapeHtml(row.state)}</div>
    </button>
  `).join("");

  return renderPanel(
    ts,
    `<p class="sub">Ciclo #${escapeHtml(ciclo.id)} · ${escapeHtml(String(activeCount))} con senal observada</p>` +
    metaBlock + `<div class="section-grid" id="historySecGrid">${gridHtml}</div>`,
  );
}

function renderHistoryActions() {
  return `<button type="button" class="history-refresh" id="refreshHistoryBtn">Actualizar</button>
    <span class="badge neutral">${historyLoadedCiclos.length} ciclos</span>`;
}

function renderCiclosPanel() {
  if (!historyLoadedCiclos.length) {
    return renderPanel(
      "Ciclos",
      renderEmpty("Sin historial de ciclos disponible."),
      renderHistoryActions(),
    );
  }

  const tbodyRows = historyLoadedCiclos.map((row) => {
    const isActive = row.id === historySelectedCicloId;
    return `<tr class="cycle-row${isActive ? " active" : ""}" data-ciclo-id="${row.id}">
      <td class="mono">${escapeHtml(row.id)}</td>
      <td class="mono">${escapeHtml(formatDateTime(row.timestamp))}</td>
    </tr>`;
  }).join("");

  const body = `<div class="table-wrap"><table>
    <thead><tr><th>#ID</th><th>Timestamp</th></tr></thead>
    <tbody id="cyclesTableBody">${tbodyRows}</tbody>
  </table></div>
  ${historyHasMore ? `<button type="button" class="load-more" id="loadMoreBtn">Cargar más ciclos</button>` : ""}`;

  return renderPanel(
    "Ciclos",
    body,
    renderHistoryActions(),
  );
}

function renderHistorialView() {
  const ciclo = historyLoadedCiclos.find((c) => c.id === historySelectedCicloId) ?? null;
  view.innerHTML = renderCiclosPanel() + renderCicloDetail(ciclo, historySelectedSecciones);
}

async function selectHistoryCiclo(cicloId) {
  const ciclo = historyLoadedCiclos.find((c) => c.id === cicloId);
  historySelectedCicloId = cicloId;
  historySelectedSecciones = null;
  setDetail("Ciclo", `#${cicloId}`, "Cargando…", formatDateTime(ciclo?.timestamp));
  renderHistorialView();

  const requestedId = cicloId;
  const shouldFetch = ciclo?.secciones_status === "ok";
  const secResult = shouldFetch
    ? await fetchJson(`${endpoints.historialSecciones}?ciclo_id=${cicloId}&limit=112`)
    : null;

  if (historySelectedCicloId !== requestedId) return;

  historySelectedSecciones = secResult === null ? [] : (secResult.ok ? asRows(secResult.data) : []);

  // Fix #5: estado claro cuando no hay secciones disponibles
  let stateText;
  if (!shouldFetch) {
    stateText = `Sin dato (${ciclo?.secciones_status ?? "sin status"})`;
  } else {
    const rows = historySelectedSecciones.length ? normalizeSections(historySelectedSecciones) : [];
    const activeCount = rows.filter((r) => r.css === "state-active").length;
    stateText = `${activeCount} secciones con senal observada`;
  }
  setDetail("Ciclo", `#${cicloId}`, stateText, formatDateTime(ciclo?.timestamp));

  renderHistorialView();
}

async function loadHistorialCiclos(reset = false) {
  if (reset) {
    historyLoadedCiclos = [];
    historySelectedCicloId = null;
    historySelectedSecciones = null;
    historyHasMore = false;
    historyAnchorTs = null;
    setDetail("-", "-", "-", "-");
  }
  const offset = historyLoadedCiclos.length;
  const hastaParam = historyAnchorTs ? `&hasta=${encodeURIComponent(historyAnchorTs)}` : "";
  const result = await fetchJson(`${endpoints.ciclos}?limit=100&offset=${offset}${hastaParam}`);
  if (!result.ok) {
    view.innerHTML = renderPanel(
      "Ciclos",
      renderEmpty(`Error al cargar historial (${result.status ? `HTTP ${result.status}` : "sin conexión"}).`),
      endpointState(result),
    );
    return;
  }
  const rows = asRows(result.data);
  if (reset && rows.length > 0) {
    historyAnchorTs = rows[0].timestamp;
  }
  historyLoadedCiclos = [...historyLoadedCiclos, ...rows];
  historyHasMore = rows.length >= 100;
  renderHistorialView();
}

async function showHistorial() {
  if (historyLoadedCiclos.length === 0) {
    await loadHistorialCiclos(true);
  } else {
    renderHistorialView();
  }
}

// --- WIRING ---------------------------------------------------------------
const view = document.getElementById("view");
const mainLayout = document.getElementById("mainLayout");
const detailHeading = document.getElementById("detailHeading");
const detailName = document.getElementById("detailName");
const detailType = document.getElementById("detailType");
const detailState = document.getElementById("detailState");
const detailTs = document.getElementById("detailTs");
const clearDetail = document.getElementById("clearDetail");

async function ensureDiagnosticoChecks() {
  if (diagnosticoChecks !== null) return;
  if (diagnosticoChecksPromise !== null) {
    await diagnosticoChecksPromise;
    return;
  }
  diagnosticoChecksPromise = fetchEndpointChecks();
  try {
    diagnosticoChecks = await diagnosticoChecksPromise;
    if (activeView === "estado") await showResumen();
  } finally {
    diagnosticoChecksPromise = null;
  }
}

const views = {
  estado: showResumen,
  secciones: showSecciones,
  historial: showHistorial,
};

const DETAIL_VIEWS = new Set(["secciones", "historial"]);

async function switchView(nextView) {
  if (!views[nextView]) return;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === nextView);
  });
  activeView = nextView;
  mainLayout.classList.toggle("has-detail", DETAIL_VIEWS.has(nextView));
  await renderActive();
  view.focus({ preventScroll: true });
}

// Fix #1: preservar scroll de ventana y celda seleccionada en auto-refresco
async function renderActive() {
  clearTimeout(refreshTimer);

  const isViewSwitch = currentViewRendered !== activeView;

  // En cambio de vista: mostrar skeleton. En auto-refresco: conservar estado.
  const savedScroll = isViewSwitch ? 0 : window.scrollY;
  const savedSelectionName = isViewSwitch
    ? null
    : document.querySelector(".section-cell.selected")?.querySelector(".section-name")?.textContent ?? null;

  if (isViewSwitch) {
    view.innerHTML = SKELETON;
  }

  view.setAttribute("aria-busy", "true");

  try {
    await views[activeView]();
    currentViewRendered = activeView;
  } finally {
    // Restaurar posición de scroll de ventana
    window.scrollTo({ top: savedScroll, behavior: "instant" });

    // Restaurar selección de cercha si había una
    if (savedSelectionName) {
      document.querySelectorAll(".section-cell").forEach((cell) => {
        if (cell.querySelector(".section-name")?.textContent === savedSelectionName) {
          cell.classList.add("selected");
        }
      });
    }

    view.setAttribute("aria-busy", "false");
    const interval = REFRESH_INTERVALS[activeView];
    if (interval) refreshTimer = setTimeout(renderActive, interval);
  }
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    switchView(button.dataset.view);
  });
});

clearDetail.addEventListener("click", () => {
  setDetail("-", "-", "-", "-");
  clearSelection();
});

view.addEventListener("click", async (event) => {
  const jump = event.target.closest("[data-jump]");
  if (jump) {
    switchView(jump.dataset.jump);
    return;
  }

  const openDiag = event.target.closest("[data-open-diagnostico]");
  if (openDiag) {
    diagnosticoOpen = true;
    await showResumen();
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    view.querySelector("[data-diagnostico]")?.scrollIntoView({
      behavior: prefersReducedMotion ? "auto" : "smooth",
    });
    await ensureDiagnosticoChecks();
    return;
  }

  const filter = event.target.closest("[data-section-filter]");
  if (filter) {
    sectionFilterState = filter.dataset.sectionFilter;
    showSecciones();
    return;
  }

  const secCell = event.target.closest(".section-cell[data-sec-name]");
  if (secCell && activeView === "secciones") {
    clearSelection();
    secCell.classList.add("selected");
    setDetail("Seccion", secCell.dataset.secName, secCell.dataset.secState, secCell.dataset.secTs);
    return;
  }

  const cicloRow = event.target.closest(".cycle-row");
  if (cicloRow) {
    selectHistoryCiclo(Number(cicloRow.dataset.cicloId));
    return;
  }

  const histSec = event.target.closest("#historySecGrid [data-sec-name]");
  if (histSec) {
    document.querySelectorAll("#historySecGrid .section-cell.selected")
      .forEach((cell) => cell.classList.remove("selected"));
    histSec.classList.add("selected");
    setDetail("Cercha (hist.)", histSec.dataset.secName, histSec.dataset.secState, histSec.dataset.secTs);
    return;
  }

  const loadMore = event.target.closest("#loadMoreBtn");
  if (loadMore) {
    loadHistorialCiclos(false);
    return;
  }

  const refreshHist = event.target.closest("#refreshHistoryBtn");
  if (refreshHist) {
    loadHistorialCiclos(true);
  }
});

view.addEventListener("input", (event) => {
  if (event.target.id !== "sectionSearch") return;
  const selectionStart = event.target.selectionStart ?? event.target.value.length;
  const selectionEnd = event.target.selectionEnd ?? event.target.value.length;
  sectionSearchTerm = event.target.value;
  clearTimeout(sectionSearchTimer);
  sectionSearchTimer = setTimeout(async () => {
    await showSecciones();
    const input = document.getElementById("sectionSearch");
    input?.focus();
    input?.setSelectionRange(
      Math.min(selectionStart, sectionSearchTerm.length),
      Math.min(selectionEnd, sectionSearchTerm.length),
    );
  }, 180);
});

view.addEventListener("toggle", async (event) => {
  if (!event.target.matches("[data-diagnostico]")) return;
  diagnosticoOpen = event.target.open;
  if (diagnosticoOpen) await ensureDiagnosticoChecks();
}, true);

renderActive();

