# Spec — Sistema Completo Fase 2: FINS → MQTT → SQLite → FastAPI → Web

**Fecha:** 2026-05-11
**Programador objetivo:** Codex (agentic)
**Estado:** Aprobado para plan de implementación

---

## Contexto del sistema

Sistema read-only de supervisión de alumbrado industrial en nave TVITEC. Lee estados de un PLC Omron CJ2M CPU32 mediante FINS/UDP y los publica a través de MQTT hacia un nodo IT donde se persisten y visualizan. El PLC nunca recibe escrituras.

### Nodos

| Nodo | Hardware | Red | Rol |
|---|---|---|---|
| OT | Raspberry Pi, Ubuntu 24.04, aarch64 | eth0: 192.168.250.56 (OT), eth1 USB-Eth: enlace IT (⚠️ PENDIENTE) | FINS reader + MQTT publisher |
| IT | Lenovo S500, Windows 10, Intel i3 | NIC1: enlace OT (⚠️ PENDIENTE), NIC2: red corporativa | Mosquitto + SQLite + FastAPI + Web |

### Restricciones absolutas
- Comunicación OT→IT únicamente (RPi publica, Lenovo nunca inicia conexión hacia RPi)
- El Lenovo no tiene visibilidad de 192.168.250.0/24
- Nunca escribir al PLC (solo Memory Area Read FINS)
- Nunca `datetime.utcnow()` — siempre `datetime.now(tz=timezone.utc)`

---

## Arquitectura general

```
PLC CJ2M (192.168.250.1)
  │  FINS/UDP cada 10s  (puerto 9600)
  ▼
[RPi — nodo OT]
  acquisition/reader.py   — lee variables PLC
  acquisition/publisher.py — construye payload, detecta cambios, publica MQTT
  │  topic: alumbrado/estado  QoS 1
  │  subred enlace 10.0.0.x
  ▼
[Lenovo — nodo IT]
  Mosquitto broker (:1883)
  subscriber/listener.py  — recibe MQTT, escribe SQLite
  SQLite bd_alumbrado.db (WAL mode)
  FastAPI (:8000)         — endpoints REST read-only
  web/index.html          — dashboard tabs (sirve FastAPI como static)
```

---

## Subsistemas independientes

Cada subsistema se implementa y testea de forma aislada. Se conectan solo al final.

| ID | Subsistema | Nodo | Dependencia de datos |
|---|---|---|---|
| A | FINS smoke test (manual, PC) | PC desarrollo | ninguna |
| B | FINS reader + MQTT publisher | RPi | datos reales de A para validar |
| C | MQTT subscriber + SQLite | Lenovo | B (puede mockearse con payload JSON) |
| D | FastAPI + Web | Lenovo | C (puede mockearse con BD prefilled) |

---

## Subsistema B — FINS reader + MQTT publisher (RPi)

### Variables PLC a leer

| Variable | Área PLC | Descripción | Tipo |
|---|---|---|---|
| H11–H17 | HR | automaticos[112] — secciones en automático | 7 words, 112 bits |
| H18–H24 | HR | manuales[112] — secciones en manual | 7 words, 112 bits |
| H25–H31 | HR | memactsec[112] — horario activo por sección | 7 words, 112 bits |
| D116 | DM | modfunalu — modo global (0=horarios, 1=fotocélula, 2=ambos) | 1 word |
| W25.bit0 | WR | entfot1 — entrada fotocélula | bit |
| H100.bit0 | HR | memfunfotalu — memoria función fotocélula | bit |
| H100.bit1 | HR | memactfotalu — memoria activación fotocélula | bit |
| D500 | DM | plc_seg ⚠️ D500/D505 INTERCAMBIADOS en PDF — usar este mapeo | 1 word |
| D501 | DM | plc_min | 1 word |
| D502 | DM | plc_hora | 1 word |
| D503 | DM | plc_dia | 1 word |
| D504 | DM | plc_mes | 1 word |
| D505 | DM | plc_anio ⚠️ ver nota D500 | 1 word |
| D506 | DM | plc_diasem | 1 word |
| D1000–D1007 | DM | horarios tramos 1-2 | 8 words — formato PENDIENTE smoke test |
| D3632–D3651 | DM | horarios fin tramos 3-12 | 20 words — formato PENDIENTE smoke test |
| A401.bit8 | AR | cycle_time_error | bit |
| A402.bit4 | AR | low_battery | bit |
| A402.bit9 | AR | io_verify_error | bit |

### Extracción de bits de sección

Función ya implementada y testeada: `acquisition/poller.py::extract_section_bits(words, group_offset)`.
- group_offset 0 → automaticos (H11–H17)
- group_offset 7 → manuales (H18–H24)
- group_offset 14 → memactsec (H25–H31)
- Incluye validación de bounds: lanza `ValueError` si `len(words) < group_offset + 7`

### Payload MQTT

Topic: `alumbrado/estado` — QoS 1 — retain: False

```json
{
  "ts": "2026-05-12T08:30:00Z",
  "fins_ok": true,
  "fins_error": null,
  "plc_reloj": {
    "seg": 0, "min": 30, "hora": 8,
    "dia": 12, "mes": 5, "anio": 2026, "diasem": 2
  },
  "modo": {
    "modfunalu": 0,
    "fotocelula_entrada": false,
    "fotocelula_mem_fun": false,
    "fotocelula_mem_act": false
  },
  "secciones": [
    {"id": 1, "automatico": true, "manual": false, "horario_activo": true},
    "... × 112"
  ],
  "horarios": {
    "raw_words": [0, 0, 0, 0, 0, 0, 0, 0]
  },
  "diagnostico": {
    "cycle_time_error": false,
    "low_battery": false,
    "io_verify_error": false
  }
}
```

Cuando `fins_ok: false`: incluir `fins_error` con mensaje, omitir o poner null el resto de campos excepto `ts`.

### Frecuencia de publicación

- Publicar si cualquier valor del payload difiere del ciclo anterior (comparación campo a campo)
- Publicar siempre si han pasado 5 minutos sin publicación (heartbeat)
- El publisher mantiene en memoria el último payload publicado para la comparación
- Primera ejecución (sin payload previo en memoria): publicar siempre
- Intervalo de lectura FINS: 10 segundos (`ACQUISITION_INTERVAL_S`)

### Ficheros RPi

| Fichero | Estado | Acción |
|---|---|---|
| `fins/client.py` | Implementado y testeado | Sin cambios |
| `fins/frame.py` | Implementado y testeado | Sin cambios |
| `acquisition/poller.py` | Tiene `extract_section_bits` | Añadir `read_all_variables()` y `build_payload()` |
| `acquisition/publisher.py` | No existe | Crear — lógica de cambio detection + paho-mqtt publish |
| `config/settings.py` | Implementado | Añadir `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`, `MQTT_TOPIC` |

---

## Subsistema C — MQTT subscriber + SQLite (Lenovo)

### Base de datos

**Fichero:** `bd_alumbrado.db` (SQLite, WAL mode, FK enforcement)
**Engine:** `model/database.py::create_db_engine(url)` — ya implementado y auditado

#### Tabla `ciclo` — una fila por ciclo FINS

| Columna | Tipo | Nullable | Descripción |
|---|---|---|---|
| id | Integer PK autoincrement | NO | |
| timestamp | DateTime(timezone=True) | NO | UTC — siempre aware |
| fins_ok | Boolean | NO | |
| fins_error | String(512) | SÍ | |
| modfunalu | Integer | SÍ | null si fins_ok=False |
| fotocelula_entrada | Boolean | SÍ | |
| fotocelula_mem_fun | Boolean | SÍ | |
| fotocelula_mem_act | Boolean | SÍ | |
| plc_seg | Integer | SÍ | D500 |
| plc_min | Integer | SÍ | D501 |
| plc_hora | Integer | SÍ | D502 |
| plc_dia | Integer | SÍ | D503 |
| plc_mes | Integer | SÍ | D504 |
| plc_anio | Integer | SÍ | D505 |
| plc_diasem | Integer | SÍ | D506 |
| cycle_time_error | Boolean | SÍ | A401.bit8 |
| low_battery | Boolean | SÍ | A402.bit4 |
| io_verify_error | Boolean | SÍ | A402.bit9 |

Índice: `ix_ciclo_timestamp (timestamp)`
Cascade en relaciones: `save-update, merge` (sin delete)

#### Tabla `seccion_estado` — 112 filas por ciclo

| Columna | Tipo | Nullable | Descripción |
|---|---|---|---|
| id | Integer PK autoincrement | NO | |
| ciclo_id | Integer FK→ciclo.id | NO | |
| timestamp | DateTime(timezone=True) | NO | UTC — denormalizado para queries sin JOIN |
| seccion_id | Integer | NO | 1–112 |
| automatico | Boolean | NO | |
| manual | Boolean | NO | |
| horario_activo | Boolean | NO | |

Índices: `ix_seccion_estado_ciclo_id (ciclo_id)`, `ix_seccion_estado_timestamp (timestamp)`, `ix_seccion_estado_seccion_timestamp (seccion_id, timestamp)`

#### Tabla `horario_tramo` — placeholder hasta smoke test

| Columna | Tipo | Nullable | Descripción |
|---|---|---|---|
| id | Integer PK autoincrement | NO | |
| ciclo_id | Integer FK→ciclo.id | NO | |
| tramo_id | Integer | NO | 1–12 |
| inicio_raw | Integer | SÍ | word raw — semántica pendiente |
| fin_raw | Integer | SÍ | word raw — semántica pendiente |

Índice: `ix_horario_tramo_ciclo_id (ciclo_id)`

### Subscriber MQTT

**Fichero nuevo:** `subscriber/listener.py`

Comportamiento:
1. Conecta a Mosquitto broker en `MQTT_BROKER_HOST:MQTT_BROKER_PORT`
2. Subscribe a `alumbrado/estado` con QoS 1
3. `on_message`: parsea JSON → construye `Ciclo` + 112 `SeccionEstado` + N `HorarioTramo` → persiste en SQLite
4. Usa su propia sesión SQLAlchemy (no compartida con FastAPI)
5. Si el JSON es malformado: loguea el error, no escribe nada, continúa escuchando
6. Si SQLAlchemy lanza excepción: loguea, hace rollback, continúa escuchando
7. `fins_ok: false` en payload → escribe solo el `Ciclo` con `fins_ok=False` y `fins_error`, sin filas de sección

**Fichero nuevo:** `subscriber/__init__.py` (vacío)

---

## Subsistema D — FastAPI + Web (Lenovo)

### FastAPI (`api/routes.py`)

**Patrón de sesión — obligatorio para thread-safety:**
```python
def get_db():
    with Session(engine) as session:
        yield session
```
Cada request HTTP tiene su propia sesión. Nunca compartir sesión entre subscriber y FastAPI.

#### Endpoints

| Método | Path | Descripción | Query params |
|---|---|---|---|
| GET | `/` | Sirve `web/index.html` | — |
| GET | `/api/estado` | Último ciclo completo | — |
| GET | `/api/secciones/actual` | 112 secciones del último ciclo | — |
| GET | `/api/horarios` | Tramos del último ciclo | — |
| GET | `/api/historial/ciclos` | Ciclos en rango temporal | `desde`, `hasta` (ISO8601 UTC), `limit` (default 200, max 1000) |
| GET | `/api/historial/secciones` | Estados históricos de sección | `seccion_id` (int, opcional), `desde`, `hasta`, `limit` |

**Queries:**

`GET /api/estado`:
```python
db.query(Ciclo).order_by(Ciclo.id.desc()).first()
```

`GET /api/secciones/actual`:
```python
ultimo = db.query(Ciclo.id).order_by(Ciclo.id.desc()).limit(1).scalar()
db.query(SeccionEstado).filter(SeccionEstado.ciclo_id == ultimo).order_by(SeccionEstado.seccion_id)
```

`GET /api/historial/secciones`:
```python
q = db.query(SeccionEstado)
if seccion_id: q = q.filter(SeccionEstado.seccion_id == seccion_id)
if desde: q = q.filter(SeccionEstado.timestamp >= desde)
if hasta: q = q.filter(SeccionEstado.timestamp <= hasta)
q.order_by(SeccionEstado.timestamp.desc()).limit(limit)
```

#### Schemas Pydantic (`schemas/lectura.py`)

```python
model_config = ConfigDict(from_attributes=True)
```

- `CicloResponse` — todos los campos de `Ciclo`
- `SeccionEstadoResponse` — `seccion_id`, `automatico`, `manual`, `horario_activo`
- `HorarioTramoResponse` — `tramo_id`, `inicio_raw`, `fin_raw`
- `SeccionHistorialResponse` — `timestamp`, `seccion_id`, `automatico`, `manual`, `horario_activo`

### Web (`web/`)

**Ficheros:**
- `web/index.html` — estructura HTML con 5 tabs
- `web/static/styles.css` — CSS con variables (colores empresa PENDIENTE, usar placeholder)
- `web/static/app.js` — fetch de API + actualización DOM

**FastAPI monta los estáticos:**
```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
app.mount("/static", StaticFiles(directory="web/static"), name="static")
```

**CSS variables placeholder (reemplazar con colores empresa mañana):**
```css
:root {
  --color-primario: #10494E;
  --color-secundario: #c8dfec;
  --color-fondo: #ffffff;
  --radio-borde: 8px;
}
```

**Refresco automático:** `setInterval` cada 15 segundos. Fetch paralelo de todos los endpoints activos del tab visible. Muestra timestamp de última actualización en cabecera.

**Banner de error:** si `fins_ok: false` en `/api/estado` → banner rojo en cabecera con `fins_error`. Los datos en tabs muestran "⚠️ Datos desactualizados — fallo FINS".

#### Tab 1 — Sistema
Cuatro tarjetas: Modo (texto + color fondo), Fotocélula (3 indicadores circulares), Reloj PLC, Diagnóstico (3 indicadores).

#### Tab 2 — Secciones
Grid CSS 16 columnas × 7 filas = 112 celdas.
- Verde: `automatico=true`
- Naranja: `manual=true`
- Azul: `horario_activo=true` (sin manual ni automatico)
- Gris: todo false
- Prioridad si múltiples activos: manual > automático > horario
- Tooltip hover: muestra los 3 bits

#### Tab 3 — Horarios
Tabla: Tramo | Inicio | Fin. Valores raw hasta confirmar formato con smoke test.

#### Tab 4 — Histórico
Filtros: sección (número 1–112, opcional) + desde/hasta (date picker, opcional). Botón "Consultar". Tabla: Timestamp | Sección | Automático | Manual | Horario. Botón "Cargar más" para paginación (`limit += 200`).

#### Tab 5 — Cerchas
Placeholder: "Pendiente de confirmar mapping sección→cercha". Tab visible, sin funcionalidad.

---

## Pendientes confirmados (no inventar, esperar datos reales)

| # | Pendiente | Bloqueado por |
|---|---|---|
| P1 | Formato real de D1000–D1007 y D3632–D3651 (horarios) | Smoke test FINS |
| P2 | Mapping sección→cercha para Tab Cerchas | Documentación PLC o smoke test |
| P3 | Colores empresa para CSS | Acceso a equipo de trabajo |
| P4 | Nombre exacto adaptador USB-Eth en RPi | Inspección física del equipo |
| P5 | Subred enlace RPi↔Lenovo (propuesta 10.0.0.x/30) | Configuración de red confirmada |

---

## Reglas obligatorias para Codex

1. **datetime**: siempre `datetime.now(tz=timezone.utc)`. Nunca `datetime.utcnow()`.
2. **Sesión FastAPI**: siempre `Depends(get_db)`. Nunca sesión global compartida.
3. **Sesión subscriber**: sesión propia, independiente de FastAPI.
4. **FINS**: solo lectura — `read_memory_area`, `read_dm_range`, `read_h_range`, `read_w_range`. Prohibido cualquier frame de escritura.
5. **Secrets**: nunca loguear connection strings, contraseñas ni contenido de `.env`.
6. **Pendientes**: los campos marcados PENDIENTE se implementan como raw integers o null. No inventar semántica.
7. **Tests**: cada módulo nuevo incluye tests unitarios. Usar mocks para MQTT y FINS en tests.
8. **Compatibilidad**: código compatible con Python 3.12.x (target RPi Ubuntu 24.04).
