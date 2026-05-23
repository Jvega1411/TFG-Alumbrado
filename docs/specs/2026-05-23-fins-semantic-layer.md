# Spec: Capa semántica FINS — Pipeline Alumbrado TVITEC

**Fecha:** 2026-05-23  
**Revisión:** 2 (correcciones semánticas tras revisión)  
**Estrategia de migración:** Clean break — schema_version=2 obligatorio, sin compatibilidad v1  
**Alcance:** acquisition (poller + decoders), subscriber (schema + listener), model, schemas API, tests

---

## Objetivo

El pipeline actual usa nombres de campo heredados del HMI que no reflejan la semántica del ladder. La capa v2 corrige esto: nombres alineados al ladder y a `Tabla_ES.html`, nuevos bloques FINS para variables no leídas (W1, H10, D102..D115, D1008/D1009, AR351..AR353, W4..W13), decodificación estructurada de horarios y reloj AR, y modelo de 160 cerchas WR separado del modelo de 112 secciones.

`fins/` queda intacto: el cliente UDP read-only y el frame ya leen por palabras y desempaquetan bits en software, que es exactamente lo que se necesita.

---

## Archivos afectados

| Archivo | Acción |
|---|---|
| `acquisition/decoders.py` | CREAR — funciones de decodificación puras |
| `acquisition/poller.py` | REFACTORIZAR — 10 bloques lógicos v2, usar decoders |
| `subscriber/payload_schema.py` | REESCRIBIR — modelos Pydantic v2, 10 bloques exactos |
| `subscriber/listener.py` | ACTUALIZAR — campos v2, nuevos bloques |
| `model/fase2.py` | ACTUALIZAR — columnas renombradas/añadidas, tablas nuevas |
| `migrations/` (Alembic) | NUEVA migración v2 |
| `schemas/lectura.py` | ACTUALIZAR — response models API |
| `tests/test_poller.py` | ACTUALIZAR — tests v2 |
| `tests/test_decoders.py` | CREAR — tests unitarios de decoders |
| `fins/` | SIN CAMBIOS |

---

## 1. Bloques FINS v2 — contrato lógico estricto

`READ_BLOCKS_V2` define exactamente 10 bloques lógicos. Un bloque lógico puede contener varias lecturas FINS (p.ej. `fotocelula` lee WR W25, HR H100 y DM D108..D115 en tres comandos separados). El validador del subscriber comprueba `set(read_status.keys()) == set(READ_BLOCKS_V2)`; cualquier conjunto distinto es mensaje inválido.

```python
READ_BLOCKS_V2 = (
    'secciones',          # HR H11..H31 (21 words → 3 grupos × 112 bits)
    'modo',               # DM D116 (modfunalu)
    'fotocelula',         # WR W25 + HR H100 + DM D108..D115
    'reloj',              # DM D500..D506 (raw + decoded + encoding configurable)
    'horarios',           # DM D1000..D1007 + D3632..D3651 (28 words → 12 tramos)
    'diagnostico',        # AR401/AR402
    'reset_temporizado',  # WR W1 + DM D102..D107
    'hmi_original',       # HR H10 + DM D1008..D1009
    'reloj_ar',           # AR351..AR353 (BCD packed channels)
    'salidas_wr',         # WR W4..W13 (10 words → 160 bits cercha_salidas)
)
```

Cualquier mensaje con los 6 bloques v1 (`secciones`, `modo`, `fotocelula`, `reloj`, `horarios`, `diagnostico` en su forma antigua) se rechaza por `schema_version: Literal[2]` y/o por el validador de `read_status`.

---

## 2. Nuevo módulo: `acquisition/decoders.py`

Funciones puras sin dependencia de FINSClient. Cubren toda la decodificación que antes estaba inline en `poller.py`.

```python
def get_bit(word: int, bit: int) -> bool:
    """Extrae bit `bit` (0=LSB) de `word`."""

def extract_section_bits(words: list[int], group_offset: int) -> list[bool]:
    """112 bits a partir de words[group_offset]. Lógica idéntica a v1."""

def decode_u32_low_high(low: int, high: int) -> int:
    """UDINT: low | (high << 16). Para variables PLC tipo UDINT (AR264/AR265, etc.)."""

def decode_i32_low_high(low: int, high: int) -> int:
    """DINT firmado: low | (high << 16) interpretado en complemento a dos.
    Usado para D102, D104, D108, D110, D112, D114 (todas DINT en Tabla_ES.html;
    el ladder usa <=SL sobre D102, confirmando signed long)."""

def bcd_byte_to_int(byte: int) -> int:
    """Decodifica un byte BCD empaquetado: ((byte>>4)*10) + (byte & 0x0F)."""

def decode_modo_label(modfunalu: int) -> str:
    """D116 modfunalu → etiqueta semántica del ladder.
    0 → 'horarios'
    1 → 'fotocelula'
    2 → 'ambos'
    otro → 'desconocido'
    NOTA: NO hay modo 'manual' en D116. El manual por sección vive en H18..H24."""

def decode_ar_clock(a351: int, a352: int, a353: int) -> dict:
    """AR351..AR353 son BCD packed channels (2 bytes BCD por word):
       A351 minsegplc → high byte = minuto,  low byte = segundo
       A352 diahorplc → high byte = día,     low byte = hora
       A353 anomesplc → high byte = año,     low byte = mes
    Devuelve {'raw': {...}, 'decoded': {...}, 'encoding': 'bcd_packed_channel'}.
    El orden high/low debe validarse con smoke real antes de fijarlo en producción."""

def decode_clock_dm(words: list[int], encoding: str = 'binary') -> dict:
    """D500..D506 reloj ladder. Encoding configurable: 'binary' (defecto) o 'bcd'.
    Devuelve {'raw_words': [...], 'encoding': encoding, 'decoded': {...}}.
    El ladder compara D504 contra +10/+11/+12 (meses), lo que sugiere binary,
    pero no se afirma como certeza absoluta — el campo encoding lo deja explícito."""

def decode_schedule_tramos(raw_words: list[int]) -> list[dict]:
    """28 raw words → lista de 12 tramos con inicio/fin/source.
    Tramos 1-2 (D1000..D1007, 8 words): inicio Y fin disponibles.
    Tramos 3-12 (D3632..D3651, 20 words = 2 words/tramo): SOLO fin.
    Cada tramo devuelto incluye: tramo, inicio_hora, inicio_minuto, fin_hora,
    fin_minuto, inicio_raw, fin_raw, source (dict con dirección DM por campo)."""

def decode_cercha_salidas(raw_words: list[int]) -> list[dict]:
    """W4..W13 (10 words) → 160 entradas cercha_salidas.
    Mapeo de bits (corregido respecto a borrador inicial):
       bits   0..111 = W4.00..W10.15 (7 words W4..W10) → cerchas 1..112
       bits 112..127 = W11.00..W11.15                  → cerchas 113..128
       bits 128..143 = W12.00..W12.15                  → cerchas 129..144
       bits 144..159 = W13.00..W13.15                  → cerchas 145..160
    Cada entrada: {id, activa, source ('W<word>.<bit>'), physical_io_confirmed: False}.
    saldigcer1..126 confirmados por Tabla_ES.html; 127..160 marcados igual pero
    sin confirmación CIO/bornera (sigue como pending_cio_map a nivel físico)."""
```

---

## 3. Refactorización `acquisition/poller.py`

### 3.1 `_read_secciones(client)` — HR H11..H31

Sin cambios estructurales en la lectura. Renombrado de campos por sección al payload (mapping a la semántica del ladder):

| Antes (v1) | Después (v2) | Fuente | Semántica ladder |
|---|---|---|---|
| `automatico` | `automatico_calculado` | H11..H17 | Bit volátil calculado |
| `manual` | `manual_activo` | H18..H24 | Comando manual latched |
| `horario_activo` | `salida_interna` | H25..H31 | Salida interna volátil |

Se añade `salida_wr: bool | None` por sección como espejo de `cercha_salidas[i].activa` para `id 1..112`. Si el bloque `salidas_wr` falla, `salida_wr = None`.

### 3.2 `_read_modo(client)` — DM D116

```python
modfunalu = words[0]
return {
    'modfunalu': modfunalu,
    'modo_label': decode_modo_label(modfunalu),  # 'horarios'|'fotocelula'|'ambos'|'desconocido'
}
```

### 3.3 `_read_fotocelula(client)` — WR W25 + HR H100 + DM D108..D115

Tres lecturas FINS, un bloque lógico:

```python
w25  = client.read_w_range(25, 1)
h100 = client.read_h_range(100, 1)
dm   = client.read_dm_range(108, 8)   # D108..D115 → 4 pares DINT
return {
    'entrada_raw': get_bit(w25, 0),
    'entrada_raw_source': 'W25.00',
    'mem_fun': get_bit(h100, 0),
    'mem_fun_source': 'H100.00',
    'filtrada_activa': get_bit(h100, 1),
    'filtrada_source': 'H100.01',
    'temporizador_activacion_s':     decode_i32_low_high(dm[0], dm[1]),  # D108/D109
    'temporizador_desactivacion_s':  decode_i32_low_high(dm[2], dm[3]),  # D110/D111
    'retardo_activacion_s':          decode_i32_low_high(dm[4], dm[5]),  # D112/D113
    'retardo_desactivacion_s':       decode_i32_low_high(dm[6], dm[7]),  # D114/D115
}
```

### 3.4 `_read_reloj(client)` — DM D500..D506

```python
raw = parse_words_to_int_list(client.read_dm_range(500, 7)['data'])
return decode_clock_dm(raw, encoding='binary')  # encoding configurable, no certeza absoluta
# Devuelve: {'raw_words': [...], 'encoding': 'binary', 'decoded': {seg, min, hora, dia, mes, anio, dia_semana}}
```

`CLOCK_DM_ENCODING` puede exponerse como constante de configuración del poller (defecto `'binary'`).

### 3.5 `_read_horarios(client)` — DM D1000..D1007 + D3632..D3651

```python
raw_1_2  = parse_words_to_int_list(client.read_dm_range(1000, 8)['data'])
raw_3_12 = parse_words_to_int_list(client.read_dm_range(3632, 20)['data'])
raw_words = raw_1_2 + raw_3_12
return {
    'raw_words': raw_words,
    'tramos': decode_schedule_tramos(raw_words),
}
```

### 3.6 `_read_diagnostico(client)` — AR401/AR402

Sin cambios funcionales:

```python
return {
    'cycle_time_error': bool((a401 >> 8) & 1),
    'low_battery':      bool((a402 >> 4) & 1),
    'io_verify_error':  bool((a402 >> 9) & 1),
}
```

*(AR264/AR265 cycle-time-value queda fuera de alcance — sólo se conservan los bits de error actuales.)*

### 3.7 `_read_reset_temporizado(client)` — WR W1 + DM D102..D107

```python
w1 = client.read_w_range(1, 1)[0]
dm = client.read_dm_range(102, 6)     # D102..D107 (D106 conapaalu, D107 reservado)
return {
    'horario_global_activo':        get_bit(w1, 1),
    'horario_global_activo_source': 'W1.01',
    'reset': {
        'activo':                        get_bit(w1, 2),
        'activo_source':                 'W1.02',
        'retardo_segundo_apagado_s':     decode_i32_low_high(dm[0], dm[1]),  # D102/D103
        'temporizador_segundo_apagado_s': decode_i32_low_high(dm[2], dm[3]), # D104/D105
        'contador_apagados':             dm[4],                              # D106 conapaalu (INT)
        'max_reintentos':                3,                                  # constante inferida del ladder
    },
}
```

`D107` queda en `raw_words` del bloque para auditoría pero sin campo semántico (reservado en Tabla_ES.html).

### 3.8 `_read_hmi_original(client)` — HR H10 + DM D1008..D1009

```python
h10 = client.read_h_range(10, 1)[0]
dm  = client.read_dm_range(1008, 2)
return {
    'indice_seccion':                          dm[0],   # D1008
    'indice_anterior':                         dm[1],   # D1009
    'automatico_seccion_seleccionada':         get_bit(h10, 12),  # H10.12 funautsec
    'manual_seccion_seleccionada':             get_bit(h10, 13),  # H10.13 marmansec
    'orden_transferencia_comun':               get_bit(h10, 14),  # H10.14 ordtraseccom
    'indicacion_activacion_alumbrado_seccion': get_bit(h10, 15),  # H10.15 indactalusec
    'h10_raw':                                 h10,
}
```

**Nota:** H10.14/H10.15 también aparecen en `Tabla_ES.html` como `selcer173/selcer174` (solape de tabla). En este programa de alumbrado el ladder los usa como `ordtraseccom`/`indactalusec`. Documentado explícitamente para evitar confusión futura.

### 3.9 `_read_reloj_ar(client)` — AR351..AR353

```python
ar = client.read_ar_range(351, 3)
return decode_ar_clock(ar[0], ar[1], ar[2])
# Devuelve: {
#   'raw':     {'A351_minsegplc': ..., 'A352_diahorplc': ..., 'A353_anomesplc': ...},
#   'decoded': {'minuto', 'segundo', 'dia', 'hora', 'anio', 'mes'},
#   'encoding': 'bcd_packed_channel',
# }
```

### 3.10 `_read_salidas_wr(client)` — WR W4..W13

```python
raw_words = parse_words_to_int_list(client.read_w_range(4, 10)['data'])
return {
    'raw_words': raw_words,                                # 10 ints, para auditoría
    'cercha_salidas': decode_cercha_salidas(raw_words),    # 160 entradas estructuradas
    'physical_io_mapping_status': 'pending_cio_map',
}
```

### 3.11 `build_payload` v2

```python
{
    'schema_version': 2,
    'ts': ...,
    'fins_ok': not failed,
    'fins_error': ...,
    'read_status': read_status,        # exactamente 10 bloques v2

    'modo': {
        'modfunalu': int,
        'modo_label': str,             # 'horarios'|'fotocelula'|'ambos'|'desconocido'
    } | None,

    'fotocelula': {
        'entrada_raw': bool, 'entrada_raw_source': 'W25.00',
        'mem_fun': bool, 'mem_fun_source': 'H100.00',
        'filtrada_activa': bool, 'filtrada_source': 'H100.01',
        'temporizador_activacion_s': int,
        'temporizador_desactivacion_s': int,
        'retardo_activacion_s': int,
        'retardo_desactivacion_s': int,
    } | None,

    'plc_reloj': {
        'raw_words': list[int],
        'encoding': str,               # 'binary' por defecto
        'decoded': {'segundo','minuto','hora','dia','mes','anio','dia_semana'},
    } | None,

    'horarios': {
        'raw_words': list[int],
        'tramos': list[TramoPayload],  # 12 entradas, con inicio/fin/source
    } | None,

    'diagnostico': {
        'cycle_time_error': bool, 'low_battery': bool, 'io_verify_error': bool,
    } | None,

    'reset_temporizado': {
        'horario_global_activo': bool,
        'horario_global_activo_source': 'W1.01',
        'reset': {
            'activo': bool, 'activo_source': 'W1.02',
            'retardo_segundo_apagado_s': int,
            'temporizador_segundo_apagado_s': int,
            'contador_apagados': int,
            'max_reintentos': 3,
        },
    } | None,

    'hmi_original': {
        'indice_seccion': int, 'indice_anterior': int,
        'automatico_seccion_seleccionada': bool,
        'manual_seccion_seleccionada': bool,
        'orden_transferencia_comun': bool,
        'indicacion_activacion_alumbrado_seccion': bool,
        'h10_raw': int,
    } | None,

    'reloj_ar': {
        'raw': {'A351_minsegplc': int, 'A352_diahorplc': int, 'A353_anomesplc': int},
        'decoded': {'minuto','segundo','dia','hora','anio','mes'},
        'encoding': 'bcd_packed_channel',
    } | None,

    'secciones': [
        {
            'id': int,
            'automatico_calculado': bool,
            'manual_activo': bool,
            'salida_interna': bool,
            'salida_wr': bool | None,           # espejo de cercha_salidas[id-1].activa
        }
    ],

    'salidas_wr': {
        'raw_words': list[int],                  # 10 ints
        'cercha_salidas': [
            {
                'id': int,                       # 1..160
                'activa': bool,
                'source': str,                   # 'W<word>.<bit>'
                'physical_io_confirmed': False,
            }
        ],
        'physical_io_mapping_status': 'pending_cio_map',
    } | None,
}
```

---

## 4. Pydantic v2 — `subscriber/payload_schema.py`

Todas las listas usan `Field(default_factory=list)`; ningún default mutable.

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

READ_BLOCKS_V2 = (
    'secciones', 'modo', 'fotocelula', 'reloj', 'horarios', 'diagnostico',
    'reset_temporizado', 'hmi_original', 'reloj_ar', 'salidas_wr',
)

class SeccionPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int
    automatico_calculado: bool
    manual_activo: bool
    salida_interna: bool
    salida_wr: bool | None = None

class TramoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tramo: int
    inicio_hora: int | None
    inicio_minuto: int | None
    fin_hora: int
    fin_minuto: int
    inicio_raw: list[int] | None = None
    fin_raw: list[int] = Field(default_factory=list)
    source: dict[str, str] = Field(default_factory=dict)

class HorariosPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw_words: list[int] = Field(default_factory=list)
    tramos: list[TramoPayload] = Field(default_factory=list)

class ModoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    modfunalu: int
    modo_label: Literal['horarios', 'fotocelula', 'ambos', 'desconocido']

class FotocelulaPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    entrada_raw: bool
    entrada_raw_source: Literal['W25.00']
    mem_fun: bool
    mem_fun_source: Literal['H100.00']
    filtrada_activa: bool
    filtrada_source: Literal['H100.01']
    temporizador_activacion_s: int
    temporizador_desactivacion_s: int
    retardo_activacion_s: int
    retardo_desactivacion_s: int

class RelojDecoded(BaseModel):
    model_config = ConfigDict(extra='forbid')
    segundo: int; minuto: int; hora: int
    dia: int; mes: int; anio: int; dia_semana: int

class RelojPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw_words: list[int] = Field(default_factory=list)
    encoding: Literal['binary', 'bcd'] = 'binary'
    decoded: RelojDecoded

class DiagnosticoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cycle_time_error: bool
    low_battery: bool
    io_verify_error: bool

class ResetSubPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    activo: bool
    activo_source: Literal['W1.02']
    retardo_segundo_apagado_s: int
    temporizador_segundo_apagado_s: int
    contador_apagados: int
    max_reintentos: int = 3

class ResetTemporizadoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    horario_global_activo: bool
    horario_global_activo_source: Literal['W1.01']
    reset: ResetSubPayload

class HmiOriginalPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    indice_seccion: int
    indice_anterior: int
    automatico_seccion_seleccionada: bool
    manual_seccion_seleccionada: bool
    orden_transferencia_comun: bool
    indicacion_activacion_alumbrado_seccion: bool
    h10_raw: int

class RelojArRaw(BaseModel):
    model_config = ConfigDict(extra='forbid')
    A351_minsegplc: int
    A352_diahorplc: int
    A353_anomesplc: int

class RelojArDecoded(BaseModel):
    model_config = ConfigDict(extra='forbid')
    minuto: int; segundo: int
    dia: int; hora: int
    anio: int; mes: int

class RelojArPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw: RelojArRaw
    decoded: RelojArDecoded
    encoding: Literal['bcd_packed_channel']

class CerchaSalidaPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int
    activa: bool
    source: str              # 'W<word>.<bit>'
    physical_io_confirmed: bool = False

class SalidasWrPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw_words: list[int] = Field(default_factory=list)
    cercha_salidas: list[CerchaSalidaPayload] = Field(default_factory=list)
    physical_io_mapping_status: Literal['pending_cio_map']

class ReadBlockStatus(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['ok', 'failed', 'absent']
    error: str | None = None

class LecturaPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[2]
    ts: str
    fins_ok: bool
    fins_error: str | None = None
    read_status: dict[str, ReadBlockStatus]

    modo: ModoPayload | None = None
    fotocelula: FotocelulaPayload | None = None
    plc_reloj: RelojPayload | None = None
    horarios: HorariosPayload | None = None
    diagnostico: DiagnosticoPayload | None = None
    reset_temporizado: ResetTemporizadoPayload | None = None
    hmi_original: HmiOriginalPayload | None = None
    reloj_ar: RelojArPayload | None = None
    secciones: list[SeccionPayload] = Field(default_factory=list)
    salidas_wr: SalidasWrPayload | None = None

    @model_validator(mode='after')
    def check_read_status_blocks(self) -> 'LecturaPayload':
        expected = set(READ_BLOCKS_V2)
        actual = set(self.read_status.keys())
        if actual != expected:
            raise ValueError(
                f"read_status v2 requiere exactamente {sorted(expected)}, recibido {sorted(actual)}"
            )
        return self
```

---

## 5. Modelo SQLite — `model/fase2.py`

### 5.1 `seccion_estado` (mantiene nombre)

Renombrar columnas + añadir `salida_wr`:

| Columna actual | Columna v2 | Acción |
|---|---|---|
| `automatico` | `automatico_calculado` | RENAME (batch_alter_table) |
| `manual` | `manual_activo` | RENAME (batch_alter_table) |
| `horario_activo` | `salida_interna` | RENAME (batch_alter_table) |
| — | `salida_wr` | ADD COLUMN BOOLEAN NULL |

### 5.2 `horario_tramo` — ampliación no destructiva

Mantener `inicio_raw`, `fin_raw` intactos. Añadir 4 columnas decodificadas **todas nullable** + backfill desde raw durante la migración:

| Columna nueva | Tipo | Nullable | Descripción |
|---|---|---|---|
| `inicio_hora` | INTEGER | SÍ | None para tramos 3-12 |
| `inicio_minuto` | INTEGER | SÍ | None para tramos 3-12 |
| `fin_hora` | INTEGER | SÍ | Backfill desde fin_raw en migración |
| `fin_minuto` | INTEGER | SÍ | Backfill desde fin_raw en migración |

No usar `server_default='0'`: falsearía históricos donde el raw original no era cero. Las nullable + backfill mantienen la verdad de los datos antiguos.

### 5.3 Tablas nuevas (1:1 con `ciclo`)

**`fotocelula_state`** — columnas:
- ciclo_id (FK)
- entrada_raw, mem_fun, filtrada_activa (BOOLEAN)
- temporizador_activacion_s, temporizador_desactivacion_s, retardo_activacion_s, retardo_desactivacion_s (INTEGER)

**`reset_temporizado_state`** — columnas:
- ciclo_id (FK)
- horario_global_activo (BOOLEAN)
- reset_activo (BOOLEAN)
- retardo_segundo_apagado_s, temporizador_segundo_apagado_s, contador_apagados (INTEGER)
- max_reintentos (INTEGER, defecto 3)

**`hmi_original_state`** — columnas:
- ciclo_id (FK)
- indice_seccion, indice_anterior, h10_raw (INTEGER)
- automatico_seccion_seleccionada, manual_seccion_seleccionada (BOOLEAN)
- orden_transferencia_comun, indicacion_activacion_alumbrado_seccion (BOOLEAN)

**`reloj_ar_state`** — columnas:
- ciclo_id (FK)
- raw_a351, raw_a352, raw_a353 (INTEGER)
- ar_minuto, ar_segundo, ar_dia, ar_hora, ar_anio, ar_mes (INTEGER)
- encoding (TEXT, default 'bcd_packed_channel')

**`salidas_wr_state`** — columnas:
- ciclo_id (FK)
- raw_words (TEXT JSON, 10 ints)
- cercha_salidas (TEXT JSON, 160 entradas serializadas)
- physical_io_mapping_status (TEXT, default 'pending_cio_map')

Se elige JSON column para `cercha_salidas` en vez de tabla detalle por cercha. 160 filas por ciclo × N ciclos/día explotaría storage sin valor analítico equivalente; el JSON mantiene los 160 estados consultables por ciclo y permite añadir tabla detalle más adelante si surge necesidad de queries por cercha individual.

### 5.4 Migración Alembic (batch mode obligatorio para SQLite)

```python
def upgrade():
    with op.batch_alter_table('seccion_estado') as batch:
        batch.alter_column('automatico',     new_column_name='automatico_calculado')
        batch.alter_column('manual',         new_column_name='manual_activo')
        batch.alter_column('horario_activo', new_column_name='salida_interna')
        batch.add_column(sa.Column('salida_wr', sa.Boolean(), nullable=True))

    with op.batch_alter_table('horario_tramo') as batch:
        batch.add_column(sa.Column('inicio_hora',   sa.Integer(), nullable=True))
        batch.add_column(sa.Column('inicio_minuto', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('fin_hora',      sa.Integer(), nullable=True))
        batch.add_column(sa.Column('fin_minuto',    sa.Integer(), nullable=True))

    # Backfill horario_tramo desde inicio_raw/fin_raw (no usa server_default).
    op.execute("""
        UPDATE horario_tramo
        SET fin_hora    = json_extract(fin_raw, '$[0]'),
            fin_minuto  = json_extract(fin_raw, '$[1]')
        WHERE fin_raw IS NOT NULL
    """)
    op.execute("""
        UPDATE horario_tramo
        SET inicio_hora   = json_extract(inicio_raw, '$[0]'),
            inicio_minuto = json_extract(inicio_raw, '$[1]')
        WHERE inicio_raw IS NOT NULL
    """)

    op.create_table('fotocelula_state',        ...)
    op.create_table('reset_temporizado_state', ...)
    op.create_table('hmi_original_state',      ...)
    op.create_table('reloj_ar_state',          ...)
    op.create_table('salidas_wr_state',        ...)
```

*(El formato exacto de `inicio_raw`/`fin_raw` en SQLite debe verificarse antes de escribir el backfill — si están como BLOB/pickle en lugar de JSON, el `UPDATE` se hace en Python iterando por filas en vez de `json_extract`.)*

---

## 6. Mapeo CIO físico — PENDIENTE explícito

`saldigcer1..126` están confirmados por `Tabla_ES.html` (`array_de_salida BOOL[160] W4.00`, `salidas_digitales WORD[10] W4`). `saldigcer127..160` aplican el mismo mapeo bit→cercha pero sin confirmación de la bornera CIO física.

Las transferencias ladder observadas:
```
XFER &6  W4  → Q:0       (W4..W9   → 6 words a salida física Q:0)
XFER &4  W10 → W400      (W10..W13 → 4 words a área de trabajo, no a Q directo)
```
confirman que las 10 words de WR existen y se transfieren, pero no resuelven el mapa físico bornera↔cercha en su totalidad.

En esta iteración:
- Todas las 160 entradas de `cercha_salidas` llevan `physical_io_confirmed: False`
- El bloque expone `physical_io_mapping_status: 'pending_cio_map'`
- No se añade columna ni tabla `cio_address` — queda como trabajo posterior cuando se confirme físicamente

---

## 7. Listener `subscriber/listener.py` — cambios

- Sustituir referencias `s.automatico`, `s.manual`, `s.horario_activo` por los nombres v2 (`automatico_calculado`, `manual_activo`, `salida_interna`)
- Escribir `salida_wr` en `seccion_estado` desde `secciones[i].salida_wr`
- Para `horario_tramo`: usar `inicio_hora/minuto` y `fin_hora/minuto` del payload `tramos[]`, mantener `inicio_raw`/`fin_raw` como serialización de `inicio_raw`/`fin_raw` del payload. Eliminar el comentario PENDIENTE P1.
- Añadir inserts a las 5 tablas nuevas: `fotocelula_state`, `reset_temporizado_state`, `hmi_original_state`, `reloj_ar_state`, `salidas_wr_state` (con `cercha_salidas` serializado a JSON).

---

## 8. API `schemas/lectura.py`

Actualizar response models para reflejar campos v2. Los renombrados de `seccion_estado` se propagan automáticamente si Pydantic usa `from_attributes=True` contra el modelo SQLAlchemy actualizado. Para las nuevas tablas, definir response models nuevos que la API pueda exponer en endpoints por ciclo (`/ciclos/{id}/fotocelula`, `/ciclos/{id}/salidas_wr`, etc., scope a definir en el plan de implementación).

---

## 9. Tests

### 9.1 `tests/test_decoders.py` (NUEVO)

- `get_bit`: extremos (bit 0, bit 15) y bits intermedios
- `extract_section_bits`: idénticos a los 8 casos actuales de `test_poller.py`
- `decode_u32_low_high`: básico + valores grandes (high=0xFFFF)
- `decode_i32_low_high`: positivos, negativo (high con MSB), borde ±2^31
- `bcd_byte_to_int`: 0x00, 0x09, 0x10, 0x99, valores no-BCD (documentar comportamiento)
- `decode_modo_label`: 0→horarios, 1→fotocelula, 2→ambos, 99→desconocido
- `decode_ar_clock`: caso conocido manual + validación de keys
- `decode_clock_dm`: encoding='binary' y encoding='bcd' (estructura, no validez de valores)
- `decode_schedule_tramos`: tramo 1 con inicio+fin, tramo 5 solo fin, source dict correcto
- `decode_cercha_salidas`: bit 0 → cercha 1 source 'W4.00'; bit 111 → cercha 112 source 'W10.15'; bit 112 → cercha 113 source 'W11.00'; bit 159 → cercha 160 source 'W13.15'

### 9.2 `tests/test_poller.py` (ACTUALIZAR)

- Actualizar fixtures FINS para incluir las nuevas lecturas (W1, H10, AR351..AR353, D102..D115, D1008..D1009, W4..W13)
- Cubrir los 10 bloques v2 individualmente (status 'ok' por bloque)
- Cubrir fallos parciales: un bloque falla, los demás se conservan
- `build_payload`: validar contra `LecturaPayload` (parseo Pydantic) en cada test
- Test específico de que `salida_wr` en cada sección refleja `cercha_salidas[id-1].activa`
- Test específico de que `read_status` contiene exactamente los 10 nombres v2

---

## 10. Despliegue

1. Detener publisher RPi
2. Detener subscriber/API Lenovo
3. Backup SQLite: `cp alumbrado.db alumbrado.db.bak.$(date +%Y%m%d-%H%M%S)`
4. Actualizar código en ambos nodos (git pull)
5. Ejecutar migración Alembic: `alembic upgrade head` (incluye backfill horario_tramo)
6. Arrancar subscriber/API Lenovo (verificar que arranca sin errores Pydantic)
7. Arrancar publisher RPi
8. Verificación primer ciclo: `read_status` con los 10 bloques v2 en `status='ok'`, modo_label coherente con D116, `cercha_salidas[0].source == 'W4.00'`

---

## 11. Fuera de alcance (deuda técnica documentada)

- Escrituras al PLC (read-only mode TFG)
- Mapeo CIO/bornera físico (`pending_cio_map` — todas las 160 cerchas con `physical_io_confirmed: False`)
- Cambios en `fins/` (transporte UDP read-only intacto)
- Compatibilidad retroactiva con schema_version=1 (clean break)
- Lectura de cycle-time-value (AR264/AR265 UDINT) — sólo se conservan los bits de error AR401/AR402
- Validación empírica del orden high/low byte en `decode_ar_clock` y del encoding real de D500..D506 (binary vs bcd): pendiente de smoke con PLC real antes de cerrar valores como fijos
- Tabla detalle por cercha individual (alternativa a JSON column en `salidas_wr_state`) — añadir si surge necesidad analítica
