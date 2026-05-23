# Spec: Capa semántica FINS — Pipeline Alumbrado TVITEC

**Fecha:** 2026-05-23  
**Estrategia de migración:** Clean break — schema_version=2 obligatorio, sin compatibilidad v1  
**Alcance:** acquisition (poller + decoders), subscriber (schema + listener), model, schemas API, tests

---

## Objetivo

El pipeline actual usa nombres de campo heredados del HMI que no reflejan el comportamiento real del PLC. La capa semántica v2 corrige esto: nombres acordes a la lógica de ladder, nuevos bloques FINS para variables no leídas actualmente, y decodificación estructurada de horarios y reloj AR. Las tablas SQLite ganan columnas sin perder los valores raw.

---

## Archivos afectados

| Archivo | Acción |
|---|---|
| `acquisition/decoders.py` | CREAR — funciones de decodificación extraídas |
| `acquisition/poller.py` | REFACTORIZAR — 10 bloques v2, usar decoders |
| `subscriber/payload_schema.py` | REESCRIBIR — modelos Pydantic v2, 10 bloques exactos |
| `subscriber/listener.py` | ACTUALIZAR — campos v2, nuevos bloques |
| `model/fase2.py` | ACTUALIZAR — columnas renombradas + añadidas, Alembic |
| `schemas/lectura.py` | ACTUALIZAR — response models API |
| `tests/test_poller.py` | ACTUALIZAR — tests v2 |
| `fins/` | SIN CAMBIOS |

---

## 1. Bloques FINS v2 — contrato estricto

`READ_BLOCKS` pasa de 6 a exactamente 10 bloques. El esquema v2 requiere **exactamente** estos 10 en `read_status`; cualquier mensaje con un conjunto distinto es inválido y se rechaza.

```python
READ_BLOCKS = (
    'secciones',          # H11..H31 (21 words, 3 groups × 112 bits)
    'modo',               # D116
    'fotocelula',         # W25 + H100
    'reloj',              # D500..D506 (7 words, binary)
    'horarios',           # D1000..D1007 + D3632..D3651 (28 words)
    'diagnostico',        # AR401/AR402
    'reset_temporizado',  # D102..D115 (14 words, 4 u32 pairs + flags)
    'hmi_original',       # D1008/D1009 (2 words)
    'reloj_ar',           # AR351..AR353 (3 words, BCD)
    'salidas_wr',         # W4..W13 (10 words, 160 bits)
)
```

El validador en `payload_schema.py` comprueba `set(read_status.keys()) == set(READ_BLOCKS)`. Un mensaje con los 6 bloques v1 se rechaza directamente.

---

## 2. Nuevo módulo: `acquisition/decoders.py`

Funciones puras sin dependencia de FINSClient. Cubren toda la decodificación que antes estaba inline en `poller.py`.

### Funciones

```python
def get_bit(word: int, bit: int) -> bool:
    """Extrae bit `bit` (0=LSB) de `word`."""

def extract_section_bits(words: list[int], group_offset: int) -> list[bool]:
    """112 bits a partir de word[group_offset]. Sin cambio de lógica respecto a v1."""

def decode_u32_low_high(low: int, high: int) -> int:
    """Combina dos words PLC en u32: value = low | (high << 16)."""

def bcd_word_to_int(word: int) -> int:
    """Decodifica BCD empaquetado de 16 bits (2 dígitos BCD por byte)."""

def decode_modo_label(modfunalu: int) -> str:
    """0→'automatico', 1→'manual', 2→'fotocelula', otro→'desconocido'."""

def decode_schedule_tramos(raw_words: list[int]) -> list[dict]:
    """
    Decodifica 28 raw words en lista de tramos estructurados.
    Tramos 1-2: D1000..D1007 (8 words) — inicio Y fin disponibles.
    Tramos 3-12: D3632..D3651 (20 words, 2 words por tramo) — solo fin disponible.
    Retorna lista[dict] con keys: tramo, inicio_hora, inicio_minuto, fin_hora, fin_minuto.
    inicio_* = None para tramos 3-12.
    """
```

---

## 3. Refactorización `acquisition/poller.py`

### Bloques nuevos

**`_read_reset_temporizado(client)`** — lee D102..D115 (14 words):
- `reset_delay_enc_ms`: decode_u32_low_high(D102, D103)
- `reset_delay_apu_ms`: decode_u32_low_high(D104, D105)
- `reset_modo`: D106 (int, 0=sin reset / 1=reset activo / otro=reservado)
- `fotoc_timer_enc_ms`: decode_u32_low_high(D108, D109)
- `fotoc_timer_apu_ms`: decode_u32_low_high(D110, D111)
- `fotoc_timer_act_ms`: decode_u32_low_high(D112, D113)
- `fotoc_timer_mem_ms`: decode_u32_low_high(D114, D115)

**`_read_hmi_original(client)`** — lee D1008/D1009 (2 words):
- `hmi_idx_a`: D1008 (int)
- `hmi_idx_b`: D1009 (int)

**`_read_reloj_ar(client)`** — lee AR351..AR353 (3 words):
- `ar_hora`: bcd_word_to_int(AR351) — hora en BCD
- `ar_min`: bcd_word_to_int(AR352) — minutos en BCD
- `ar_seg`: bcd_word_to_int(AR353) — segundos en BCD

**`_read_salidas_wr(client)`** — lee W4..W13 (10 words):
- `salidas_wr_raw`: lista de 10 int (para auditoría)
- `salida_wr_por_seccion`: lista[bool | None], 112 entradas (secciones 1-112); bits 0-111 de W4..W11.15
- Bits 112-125 (saldigcer113-126, W11.0..W11.13) son confirmados por Tabla_ES.html pero quedan fuera del modelo de secciones → incluidos en `raw_extra`
- Bits 126-159 (W12..W13) = PENDIENTE, sin mapeo confirmado → `raw_extra`

### Campo renombrado en `_read_secciones`

| Antes (v1) | Después (v2) | Fuente PLC | Semántica |
|---|---|---|---|
| `automatico` | `automatico_calculado` | H11..H17 | Bit volátil calculado por ladder |
| `manual` | `manual_activo` | H18..H24 | Comando manual latched |
| `horario_activo` | `salida_interna` | H25..H31 | Salida interna volátil |

Se añade `salida_wr: bool | None` por sección, tomado de `salida_wr_por_seccion[i]` del bloque `salidas_wr`.

### `build_payload` v2

```python
{
    'schema_version': 2,
    'ts': ...,
    'fins_ok': ...,
    'fins_error': ...,
    'read_status': read_status,        # exactamente 10 bloques
    'plc_reloj': { ... },              # sin cambio estructural
    'modo': { modfunalu, modo_label, fotocelula_* },
    'secciones': [
        {
            'id': int,
            'automatico_calculado': bool,
            'manual_activo': bool,
            'salida_interna': bool,
            'salida_wr': bool | None,  # None si bloque salidas_wr falló
        }
    ],
    'horarios': {
        'raw_words': list[int],        # 28 words, sin cambio
        'tramos': list[dict],          # decodificado por decode_schedule_tramos
    },
    'diagnostico': { cycle_time_error, low_battery, io_verify_error },
    'reset_temporizado': { reset_delay_enc_ms, reset_delay_apu_ms, reset_modo,
                           fotoc_timer_enc_ms, fotoc_timer_apu_ms,
                           fotoc_timer_act_ms, fotoc_timer_mem_ms },
    'hmi_original': { hmi_idx_a, hmi_idx_b },
    'reloj_ar': { ar_hora, ar_min, ar_seg },
    'salidas_wr': {
        'salidas_wr_raw': list[int],   # 10 words
        'raw_extra': list[int],        # bits 112-159, para auditoría
    },
}
```

---

## 4. Pydantic v2 — `subscriber/payload_schema.py`

### Cambios clave

```python
class SeccionPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int
    automatico_calculado: bool
    manual_activo: bool
    salida_interna: bool
    salida_wr: bool | None = None

class HorariosPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw_words: list[int]
    tramos: list[TramoPayload]

class TramoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tramo: int
    inicio_hora: int | None
    inicio_minuto: int | None
    fin_hora: int
    fin_minuto: int

class ResetTemporizadoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reset_delay_enc_ms: int
    reset_delay_apu_ms: int
    reset_modo: int
    fotoc_timer_enc_ms: int
    fotoc_timer_apu_ms: int
    fotoc_timer_act_ms: int
    fotoc_timer_mem_ms: int

class HmiOriginalPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    hmi_idx_a: int
    hmi_idx_b: int

class RelojArPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ar_hora: int
    ar_min: int
    ar_seg: int

class SalidasWrPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    salidas_wr_raw: list[int]
    raw_extra: list[int]

class LecturaPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[2]
    ts: str
    fins_ok: bool
    fins_error: str | None = None
    read_status: dict[str, ReadBlockStatus]
    plc_reloj: RelojPayload | None = None
    modo: ModoPayload | None = None
    secciones: list[SeccionPayload] = []
    horarios: HorariosPayload | None = None
    diagnostico: DiagnosticoPayload | None = None
    reset_temporizado: ResetTemporizadoPayload | None = None
    hmi_original: HmiOriginalPayload | None = None
    reloj_ar: RelojArPayload | None = None
    salidas_wr: SalidasWrPayload | None = None

    @model_validator(mode='after')
    def check_read_status_blocks(self) -> 'LecturaPayload':
        expected = set(READ_BLOCKS_V2)  # los 10 bloques exactos
        actual = set(self.read_status.keys())
        if actual != expected:
            raise ValueError(f"read_status debe tener exactamente {expected}, recibido {actual}")
        return self
```

`schema_version: Literal[2]` rechaza automáticamente cualquier mensaje v1.

---

## 5. Modelo SQLite — `model/fase2.py`

### Tabla `seccion_estado` (mantiene nombre)

Renombrar columnas + añadir `salida_wr`:

| Columna actual | Columna v2 | Acción |
|---|---|---|
| `automatico` | `automatico_calculado` | RENAME (Alembic batch) |
| `manual` | `manual_activo` | RENAME (Alembic batch) |
| `horario_activo` | `salida_interna` | RENAME (Alembic batch) |
| — | `salida_wr` | ADD COLUMN BOOLEAN NULL |

### Tabla `horario_tramo` (ampliación no destructiva)

Mantener `inicio_raw` y `fin_raw` intactos. Añadir columnas decodificadas:

| Columna nueva | Tipo | Nullable | Descripción |
|---|---|---|---|
| `inicio_hora` | INTEGER | SÍ | Hora inicio (None para tramos 3-12) |
| `inicio_minuto` | INTEGER | SÍ | Minuto inicio (None para tramos 3-12) |
| `fin_hora` | INTEGER | NO | Hora fin |
| `fin_minuto` | INTEGER | NO | Minuto fin |

### Tablas nuevas

**`reset_temporizado`** — una fila por ciclo (ciclo_id FK):
- `reset_delay_enc_ms`, `reset_delay_apu_ms`, `reset_modo`
- `fotoc_timer_enc_ms`, `fotoc_timer_apu_ms`, `fotoc_timer_act_ms`, `fotoc_timer_mem_ms`

**`hmi_original`** — una fila por ciclo:
- `hmi_idx_a`, `hmi_idx_b`

**`reloj_ar`** — una fila por ciclo:
- `ar_hora`, `ar_min`, `ar_seg`

**`salidas_wr`** — una fila por ciclo:
- `salidas_wr_raw` (JSON / BLOB, 10 int)
- `raw_extra` (JSON / BLOB, bits 112-159)

### Migración Alembic

Usar `batch_alter_table` (obligatorio para SQLite — no soporta ALTER COLUMN directo):

```python
with op.batch_alter_table('seccion_estado') as batch_op:
    batch_op.alter_column('automatico', new_column_name='automatico_calculado')
    batch_op.alter_column('manual', new_column_name='manual_activo')
    batch_op.alter_column('horario_activo', new_column_name='salida_interna')
    batch_op.add_column(sa.Column('salida_wr', sa.Boolean(), nullable=True))

with op.batch_alter_table('horario_tramo') as batch_op:
    batch_op.add_column(sa.Column('inicio_hora', sa.Integer(), nullable=True))
    batch_op.add_column(sa.Column('inicio_minuto', sa.Integer(), nullable=True))
    batch_op.add_column(sa.Column('fin_hora', sa.Integer(), nullable=False, server_default='0'))
    batch_op.add_column(sa.Column('fin_minuto', sa.Integer(), nullable=False, server_default='0'))
```

---

## 6. Mapeo CIO físico — PENDIENTE

Las salidas físicas por bornera no están confirmadas. El mapeo provisional `saldigcer1..126 = W4.00..W11.13` viene de Tabla_ES.html y es suficiente para el modelo de secciones (112 bits). Las secciones 113-160 quedan en `raw_extra`.

No se crea tabla ni columna `physical_io` en esta iteración. Se documenta como deuda técnica:

```
physical_io.confirmed = false
physical_io.cio_address = null
physical_io.mapping_status = 'pending_cio_map'
```

---

## 7. Listener `subscriber/listener.py` — cambios

- Usar campos v2: `s.automatico_calculado`, `s.manual_activo`, `s.salida_interna`, `s.salida_wr`
- Escribir filas en las 4 tablas nuevas (reset_temporizado, hmi_original, reloj_ar, salidas_wr)
- Usar `tramos` del payload para poblar `horario_tramo` con columnas decodificadas; mantener `inicio_raw`/`fin_raw`

---

## 8. API `schemas/lectura.py`

Actualizar response models para reflejar campos v2. No hay cambio de ruta ni versión de API en esta iteración — la API ya solo sirve datos desde SQLite, y las columnas renombradas se reflejan automáticamente si los modelos Pydantic coinciden.

---

## 9. Tests `tests/test_poller.py`

- Actualizar los 8 casos de `extract_section_bits` (sin cambio de lógica, solo mover a decoders)
- Actualizar los 14 casos de `read_all_variables` con los 10 bloques v2
- Actualizar los 13 casos de `build_payload` con campos v2 y estructura nueva
- Añadir tests unitarios para cada función en `decoders.py`
- Añadir tests para `decode_schedule_tramos` (tramos 1-2 con inicio, tramos 3-12 sin inicio)

---

## 10. Despliegue

Secuencia obligatoria para no perder datos:

1. Detener publisher RPi
2. Detener subscriber/API Lenovo
3. Backup SQLite: `cp alumbrado.db alumbrado.db.bak.$(date +%Y%m%d)`
4. Actualizar código en ambos nodos (git pull)
5. Ejecutar migración Alembic: `alembic upgrade head`
6. Arrancar subscriber/API Lenovo
7. Arrancar publisher RPi
8. Verificar: `read_status` con 10 bloques ok en el primer ciclo

---

## Fuera de alcance

- Escrituras al PLC (read-only mode)
- Mapeo físico CIO/bornera (pending_cio_map)
- Cambios en `fins/` (transporte FINS sin tocar)
- Compatibilidad retroactiva con schema_version=1
