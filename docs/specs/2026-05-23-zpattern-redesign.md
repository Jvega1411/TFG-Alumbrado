# Spec: Rediseño Z-pattern — Dashboard Alumbrado TVITEC

**Fecha:** 2026-05-23  
**Enfoque elegido:** Opción B — Panel Z en dos columnas  
**Alcance:** Todas las vistas (Estado, Secciones, Historial)  
**Densidad:** Compacto

**Nota V3 observable (2026-05-29):** este documento es historico para layout.
Las etiquetas `Activas`/`Apagadas` usadas abajo pertenecen a la UI anterior;
la UI vigente debe hablar de `senal observada` / `sin senal observada` y no de
estado fisico final.

---

## Objetivo

Reducir el espacio en blanco sin propósito, consolidar información redundante y estructurar el contenido siguiendo el patrón de lectura Z (arriba-izquierda → arriba-derecha → diagonal → abajo-derecha). El cambio más visible es en la vista Estado, que pasa de tres paneles apilados a un único panel con layout en dos columnas.

---

## Archivos afectados

- `web/static/styles.css` — cambios de spacing + nuevas clases estructurales
- `web/static/app.js` — función `showResumen()` refactorizada; resto de vistas sin cambio estructural

---

## 1. Cambios de espaciado globales (todas las vistas)

Aplicar en `styles.css`. Afectan Estado, Secciones e Historial.

| Selector | Propiedad | Antes | Después |
|---|---|---|---|
| `.shell` | `padding` | `16px 0 28px` | `8px 0 16px` |
| `.panel` | `padding` | `16px` | `12px` |
| `.panel + .panel` | `margin-top` | `14px` | `8px` |
| `.panel-head` | `margin-bottom` | `14px` | `8px` |
| `.metric` | `min-height` | `104px` | _(eliminado)_ |
| `.ops-primary` | `min-height` | `128px` | `80px` |
| `.section-cell` | `min-height` | `76px` | `60px` |
| `.tabs` | `margin` | `12px 0` | `6px 0` |
| `.tab` | `min-height` | `44px` | `36px` |
| `th, td` | `padding` | `10px` | `7px 8px` |
| `.kv` | `padding` | `9px 0` | `5px 0` |

---

## 2. Cambios estructurales — Vista Estado

### 2a. CSS: nuevas clases

Añadir en `styles.css`:

```css
/* Layout Z de dos columnas para vista Estado */
.estado-grid {
  display: grid;
  grid-template-columns: minmax(180px, 0.42fr) minmax(0, 0.58fr);
  gap: 12px;
  margin-bottom: 10px;
  align-items: start;
}
.estado-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.estado-right {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Fila de acciones al pie del panel */
.estado-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}
```

Responsive: en `@media (max-width: 720px)` añadir:
```css
.estado-grid {
  grid-template-columns: 1fr;
}
```

### 2b. JS: refactorizar `showResumen()`

La función actualmente genera 3 paneles + 1 `<details>`. Pasa a generar:
- 1 panel "Estado" con el layout Z (ver estructura HTML abajo)
- 1 `<details>` "Diagnóstico" (sin cambio)

**Estructura HTML del nuevo panel Estado:**

```html
<section class="panel">
  <div class="panel-head">
    <div><h2>Estado</h2></div>
    <div class="panel-action"><!-- endpointState + badge con dato --></div>
  </div>

  <div class="estado-grid">
    <!-- Columna izquierda: Salud + Avisos -->
    <div class="estado-left">
      <!-- ops-primary con healthClass (ok/warn/bad) -->
      <div class="ops-primary">
        <span>Estado de datos</span>
        <strong><!-- healthLabel --></strong>
        <small><!-- freshnessHint --></small>
      </div>
      <!-- Lista de anomalías o empty.success -->
      <!-- si anomalies.length > 0: .alert-list -->
      <!-- si no: .empty.success -->
    </div>

    <!-- Columna derecha: 4 métricas + 3 relojes -->
    <div class="estado-right">
      <!-- grid 2×2 con section-summary (activas, apagadas, fallos, sin dato) -->
      <div class="section-summary">
        <!-- metric("Activas", ...) -->
        <!-- metric("Apagadas", ...) -->
        <!-- metric("Fallos", ...) -->
        <!-- metric("Sin datos", ...) -->
      </div>
      <!-- 3 relojes RPi / PLC / UI -->
      <div class="sys-clocks">
        <!-- RPi, PLC, UI -->
      </div>
    </div>
  </div>

  <!-- Acciones al pie -->
  <div class="estado-actions">
    <button data-jump="secciones" class="secondary-action">Abrir secciones</button>
    <button data-jump="historial" class="secondary-action">Ver historial</button>
    <button data-open-diagnostico class="secondary-action">Diagnóstico</button>
  </div>
</section>
```

### 2c. Elementos eliminados de `showResumen()`

Estos elementos del HTML generado dejan de existir:

| Elemento | Motivo |
|---|---|
| `sys-status-row` (badges API OK / FINS / frescura) | Redundante con columna izquierda |
| Panel "Avisos" separado | Integrado en columna izquierda |
| Panel "Secciones" separado | Métricas integradas en columna derecha; acciones al pie |
| `ops-kpis` con FINS + frescura + activas | Reemplazado por grid 2×2 de secciones |
| `sys-blocks` (lista kv de bloques FINS) | Eliminado — los fallos de bloque ya aparecen en la lista de avisos (via `anomalyItems()`); el estado global FINS está en el texto secundario del hero; los detalles completos siguen en el panel Diagnóstico |

### 2d. Elementos conservados sin cambio

- `ops-primary` con `healthClass` (ok/warn/bad) — mismo lógica de color
- `renderDiagnosticoSection()` — sin tocar
- `anomalyItems()` — sin tocar; los avisos se muestran en la columna izquierda
- `finsState()` — sin tocar
- Toda la lógica de `blockBadge()`, `freshnessHint`, `formatAge()`

---

## 3. Vistas Secciones e Historial

Solo se benefician de los cambios de spacing globales (Sección 1). No hay cambios estructurales en:
- `showSecciones()` — sin cambio
- `showHistorial()` / `renderHistorialView()` — sin cambio
- `renderCicloDetail()` — sin cambio

---

## 4. Patrón Z resultante en vista Estado

```
① ops-primary "Sin avisos / N avisos"     →→→  ② 4 métricas (Activas/Apagadas/Fallos/Sin dato)
   [columna izquierda, arriba]                   [columna derecha, arriba]

   [alertas o empty.success]              ↘↘↘  [3 relojes RPi / PLC / UI]
   [columna izquierda, abajo]                   [columna derecha, abajo]

③→④ [Acciones: Secciones → | Historial → | Diagnóstico]    [esquina derecha del pie]
```

---

## 5. Criterios de éxito

- [ ] La vista Estado cabe en una sola pantalla sin scroll en 1280×800
- [ ] El estado de salud ("Sin avisos" o "N avisos") es lo primero visible al cargar
- [ ] Los 4 KPIs de secciones están visibles en el primer vistazo sin scroll
- [ ] La vista Secciones muestra más celdas en pantalla (min-height reducido)
- [ ] No hay regresión visual en mobile (≤720px): el grid Z colapsa a columna única
- [ ] El panel Diagnóstico sigue funcionando (toggle, endpoint checks)
