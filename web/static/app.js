const SECTION_COUNT = 112;

const endpoints = {
  estado: "/api/estado",
  secciones: "/api/secciones/actual",
  horarios: "/api/horarios",
  ciclos: "/api/historial/ciclos",
  historialSecciones: "/api/historial/secciones",
};

const view = document.getElementById("view");
const topStatus = document.getElementById("topStatus");
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
    if (!response.ok) {
      return { ok: false, status: response.status, data: null };
    }
    return { ok: true, status: response.status, data: await response.json() };
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

function getTimestamp(item) {
  return item?.timestamp || item?.ts || item?.created_at || item?.fecha || "-";
}

function fieldValue(item, names) {
  for (const name of names) {
    if (item && item[name] !== undefined && item[name] !== null) return item[name];
  }
  return null;
}

function blockStatus(ciclo, block) {
  if (!ciclo || typeof ciclo !== "object") return null;
  return ciclo[`${block}_status`] ?? null;
}

function blockOk(ciclo, block) {
  const status = blockStatus(ciclo, block);
  if (status === null) return fieldValue(ciclo, ["fins_ok", "lectura_ok"]) === true;
  return status === "ok";
}

function blockBadge(ciclo, block) {
  const status = blockStatus(ciclo, block);
  if (status === "ok") return badge("OK", "ok");
  if (status === "failed") return badge("FALLO", "bad");
  if (status === "absent") return badge("AUSENTE", "warn");
  return badge("SIN ESTADO", "warn");
}

function badge(text, cls = "") {
  return `<span class="badge ${cls}">${escapeHtml(text)}</span>`;
}

function endpointState(result) {
  if (result.ok) return badge("OK", "ok");
  if (result.status === 404) return badge("PENDIENTE API", "warn");
  if (result.status === 0) return badge("SIN CONEXION", "bad");
  return badge(`HTTP ${result.status}`, "bad");
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
    return {
      index,
      name,
      state: String(explicitState),
      css: "state-ok",
      ts: getTimestamp(item),
    };
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
    state: flags.length ? flags.join(" + ") : "Sin datos",
    css: flags.length ? "state-ok" : "state-unknown",
    ts: getTimestamp(item),
  };
}

function renderPanel(title, sub, body, right = "") {
  return `
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>${escapeHtml(title)}</h2>
          <p class="sub">${escapeHtml(sub)}</p>
        </div>
        <div>${right}</div>
      </div>
      ${body}
    </section>
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

function renderEmpty(text) {
  return `<div class="empty">${escapeHtml(text)}</div>`;
}

function metric(label, value) {
  return `
    <div class="metric">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${value}</div>
    </div>
  `;
}

async function showResumen() {
  const [estado, secciones, horarios] = await Promise.all([
    fetchJson(endpoints.estado),
    fetchJson(endpoints.secciones),
    fetchJson(endpoints.horarios),
  ]);

  const estadoData = estado.data || {};
  const sectionRows = normalizeSections(secciones.data);
  const withData = sectionRows.filter((row) => row.state !== "Sin datos").length;
  const horarioRows = asRows(horarios.data);

  const finsOk = fieldValue(estadoData, ["fins_ok", "lectura_ok"]);
  const hasOkBlock = ["secciones", "horarios", "modo", "fotocelula", "reloj", "diagnostico"]
    .some((name) => blockOk(estadoData, name));
  const finsText = finsOk === true ? "OK" : hasOkBlock ? "PARCIAL" : finsOk === false ? "FALLO" : "PENDIENTE";
  const finsClass = finsOk === true ? "ok" : hasOkBlock ? "warn" : finsOk === false ? "bad" : "warn";
  topStatus.innerHTML = estado.ok ? badge(finsText, finsClass) : endpointState(estado);

  view.innerHTML =
    renderPanel("Resumen", "Estado de adquisicion y frescura de datos", `
      <div class="status-grid">
        ${metric("API estado", endpointState(estado))}
        ${metric("FINS", badge(finsText, finsClass))}
        ${metric("Secciones con dato", escapeHtml(`${withData}/${SECTION_COUNT}`))}
        ${metric("Horarios recibidos", escapeHtml(String(horarioRows.length)))}
      </div>
    `) +
    renderPanel("Ultima lectura", "Valores publicados por la API si existen", `
      ${renderKeyValues([
        ["Timestamp", escapeHtml(getTimestamp(estadoData))],
        ["Error FINS", escapeHtml(fieldValue(estadoData, ["fins_error", "error_msg", "error"]) || "-")],
        ["Modo", blockBadge(estadoData, "modo")],
        ["Fotocelula", blockBadge(estadoData, "fotocelula")],
        ["Reloj PLC", blockBadge(estadoData, "reloj")],
        ["Secciones", blockBadge(estadoData, "secciones")],
        ["Horarios", blockBadge(estadoData, "horarios")],
        ["Diagnostico", blockBadge(estadoData, "diagnostico")],
      ])}
    `) +
    renderPanel("Contrato API", "Solo endpoints GET read-only", `
      ${renderKeyValues([
        [endpoints.estado, endpointState(estado)],
        [endpoints.secciones, endpointState(secciones)],
        [endpoints.horarios, endpointState(horarios)],
      ])}
    `);
}

async function showSecciones() {
  const result = await fetchJson(endpoints.secciones);
  const rows = normalizeSections(result.data);

  view.innerHTML = renderPanel(
    "Secciones",
    "112 secciones. Sin datos no implica estado real.",
    `<div class="section-grid" id="sectionGrid"></div>`,
    endpointState(result),
  );

  const grid = document.getElementById("sectionGrid");
  rows.forEach((row) => {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = `section-cell ${row.css}`;
    cell.innerHTML = `
      <div class="section-name">${escapeHtml(row.name)}</div>
      <div class="section-state">${escapeHtml(row.state)}</div>
    `;
    cell.addEventListener("click", () => {
      clearSelection();
      cell.classList.add("selected");
      setDetail("Seccion", row.name, row.state, row.ts);
    });
    grid.appendChild(cell);
  });
}

async function showHorarios() {
  const result = await fetchJson(endpoints.horarios);
  const rows = asRows(result.data);

  const body = rows.length
    ? `<div class="table-wrap"><table>
        <thead><tr><th>Clave</th><th>Valor</th><th>Timestamp</th></tr></thead>
        <tbody>
          ${rows.map((row, index) => `
            <tr>
              <td class="mono">${escapeHtml(row?.tramo_id ?? row?.id ?? row?.tramo ?? index + 1)}</td>
              <td class="mono">${escapeHtml(JSON.stringify(row))}</td>
              <td class="mono">${escapeHtml(getTimestamp(row))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table></div>`
    : renderEmpty("Sin horarios disponibles. Semantica D1000/D3632 PENDIENTE.");

  view.innerHTML = renderPanel("Horarios", "Datos raw hasta confirmar semantica PLC", body, endpointState(result));
}

async function showHistorial() {
  const [ciclos, secciones] = await Promise.all([
    fetchJson(endpoints.ciclos),
    fetchJson(endpoints.historialSecciones),
  ]);

  view.innerHTML =
    renderHistoryTable("Historial de ciclos", endpoints.ciclos, ciclos) +
    renderHistoryTable("Historial de secciones", endpoints.historialSecciones, secciones);
}

function renderHistoryTable(title, endpoint, result) {
  const rows = asRows(result.data).slice(0, 50);
  const body = rows.length
    ? `<div class="table-wrap"><table>
        <thead><tr><th>#</th><th>Timestamp</th><th>Dato</th></tr></thead>
        <tbody>
          ${rows.map((row, index) => `
            <tr>
              <td class="mono">${index + 1}</td>
              <td class="mono">${escapeHtml(getTimestamp(row))}</td>
              <td class="mono">${escapeHtml(JSON.stringify(row))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table></div>`
    : renderEmpty("Sin historial disponible.");

  return renderPanel(title, endpoint, body, endpointState(result));
}

async function showDiagnostico() {
  const checks = await Promise.all(Object.entries(endpoints).map(async ([name, path]) => {
    const result = await fetchJson(path);
    return [name, path, result];
  }));

  const body = `<div class="table-wrap"><table>
    <thead><tr><th>Recurso</th><th>Endpoint</th><th>Estado</th></tr></thead>
    <tbody>
      ${checks.map(([name, path, result]) => `
        <tr>
          <td>${escapeHtml(name)}</td>
          <td class="mono">${escapeHtml(path)}</td>
          <td>${endpointState(result)}</td>
        </tr>
      `).join("")}
    </tbody>
  </table></div>`;

  view.innerHTML = renderPanel("Diagnostico", "Comprobacion pasiva de endpoints read-only", body);
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
  await views[activeView]();
  refreshTimer = setTimeout(renderActive, activeView === "resumen" ? 5000 : 10000);
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
