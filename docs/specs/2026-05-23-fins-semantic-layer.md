# Spec: Capa semántica FINS — Pipeline Alumbrado TVITEC

**Fecha:** 2026-05-23  
**Revisión:** 3 (ajustes de contrato/implementación: helper words(), strict types, validadores semánticos, JSON columns para horario_tramo)  
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
| `alembic/versions/` | NUEVA revisión v2 (`20260524_0003_v2_semantic_layer.py`) |
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
from fins.frame import parse_words_to_int_list

def words(response: dict) -> list[int]:
    """Helper único para extraer la lista de words de una respuesta FINS.
    FINSClient.read_*_range() devuelve dict con clave 'data' (bytes); siempre
    hay que pasar por parse_words_to_int_list. Esta función centraliza esa
    conversión para que ningún snippet del poller use response['data'] ni
    response[0] directamente."""
    return parse_words_to_int_list(response["data"])

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
    """Decodifica un byte BCD empaquetado: ((byte>>4)*10) + (byte & 0x0F).
    Rechaza nibbles > 9 con ValueError. Si AR351..AR353 trae un valor no-BCD
    (PLC en estado inconsistente), el bloque reloj_ar debe marcarse como
    failed; no se publica una hora falsa."""

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
    Mapeo de bits:
       bits   0..111 = W4.00..W10.15 (7 words W4..W10) → cerchas 1..112
       bits 112..127 = W11.00..W11.15                  → cerchas 113..128
       bits 128..143 = W12.00..W12.15                  → cerchas 129..144
       bits 144..159 = W13.00..W13.15                  → cerchas 145..160
    Cada entrada: {id, activa, source ('W<word>.<bit>'), physical_io_confirmed: False}.

    Nomenclatura del símbolo PLC: Tabla_ES.html confirma saldigcer1..126 con
    direcciones W4.00..W11.13. Las cerchas 127..160 NO se nombran como
    saldigcer127..160 en esta spec (esos símbolos no están confirmados en la
    tabla local). Se exponen como cercha_salidas[127..160] con WR source
    conocido y mapeo de símbolo/bornera pendiente (pending_cio_map)."""
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
modfunalu = words(client.read_dm_range(116, 1))[0]
return {
    'modfunalu': modfunalu,
    'modo_label': decode_modo_label(modfunalu),  # 'horarios'|'fotocelula'|'ambos'|'desconocido'
}
```

### 3.3 `_read_fotocelula(client)` — WR W25 + HR H100 + DM D108..D115

Tres lecturas FINS, un bloque lógico:

```python
w25  = words(client.read_w_range(25, 1))[0]
h100 = words(client.read_h_range(100, 1))[0]
dm   = words(client.read_dm_range(108, 8))   # D108..D115 → 4 pares DINT
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
raw = words(client.read_dm_range(500, 7))
return decode_clock_dm(raw, encoding='binary')  # encoding configurable, no certeza absoluta
# Devuelve: {'raw_words': [...], 'encoding': 'binary', 'decoded': {seg, min, hora, dia, mes, anio, dia_semana}}
```

`CLOCK_DM_ENCODING` puede exponerse como constante de configuración del poller (defecto `'binary'`).

### 3.5 `_read_horarios(client)` — DM D1000..D1007 + D3632..D3651

```python
raw_1_2  = words(client.read_dm_range(1000, 8))
raw_3_12 = words(client.read_dm_range(3632, 20))
raw_words = raw_1_2 + raw_3_12
return {
    'raw_words': raw_words,
    'tramos': decode_schedule_tramos(raw_words),
}
```

### 3.6 `_read_diagnostico(client)` — AR401/AR402

Sin cambios funcionales:

```python
a401 = words(client.read_ar_range(401, 1))[0]
a402 = words(client.read_ar_range(402, 1))[0]
return {
    'cycle_time_error': bool((a401 >> 8) & 1),
    'low_battery':      bool((a402 >> 4) & 1),
    'io_verify_error':  bool((a402 >> 9) & 1),
}
```

*(AR264/AR265 cycle-time-value queda fuera de alcance — sólo se conservan los bits de error actuales.)*

### 3.7 `_read_reset_temporizado(client)` — WR W1 + DM D102..D107

```python
w1_raw = words(client.read_w_range(1, 1))[0]
dm = words(client.read_dm_range(102, 6))   # D102..D107 (D106 conapaalu; D107 sin mapeo confirmado)
return {
    'w1_raw': w1_raw,
    'dm_raw_words': dm,                                   # 6 ints D102..D107 para auditoría
    'horario_global_activo':        get_bit(w1_raw, 1),
    'horario_global_activo_source': 'W1.01',
    'reset': {
        'activo':                        get_bit(w1_raw, 2),
        'activo_source':                 'W1.02',
        'retardo_segundo_apagado_s':     decode_i32_low_high(dm[0], dm[1]),  # D102/D103
        'temporizador_segundo_apagado_s': decode_i32_low_high(dm[2], dm[3]), # D104/D105
        'contador_apagados':             dm[4],                              # D106 conapaalu (INT)
        'max_reintentos':                3,                                  # constante inferida del ladder
    },
}
```

`D107` carece de mapeo confirmado en `Tabla_ES.html` (no se afirma "reservado"). Queda accesible vía `dm_raw_words[5]` para auditoría, sin campo semántico expuesto. Si en el futuro se confirma su función, se le añade campo nominado sin romper el contrato.

### 3.8 `_read_hmi_original(client)` — HR H10 + DM D1008..D1009

```python
h10 = words(client.read_h_range(10, 1))[0]
dm  = words(client.read_dm_range(1008, 2))
return {
    'indice_seccion':                          dm[0],   # D1008 (índice PLC raw, ver §6 Indexación)
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
ar = words(client.read_ar_range(351, 3))
return decode_ar_clock(ar[0], ar[1], ar[2])
# Devuelve: {
#   'raw':     {'A351_minsegplc': ..., 'A352_diahorplc': ..., 'A353_anomesplc': ...},
#   'decoded': {'minuto', 'segundo', 'dia', 'hora', 'anio', 'mes'},
#   'encoding': 'bcd_packed_channel',
# }
# Si bcd_byte_to_int lanza ValueError (nibble > 9), el bloque queda 'failed'
# y reloj_ar=None en el payload (no se publica una hora falsa).
```

### 3.10 `_read_salidas_wr(client)` — WR W4..W13

```python
raw = words(client.read_w_range(4, 10))                # 10 ints W4..W13
return {
    'raw_words': raw,                                  # para auditoría
    'cercha_salidas': decode_cercha_salidas(raw),      # 160 entradas estructuradas
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
        'w1_raw': int,
        'dm_raw_words': list[int],                 # exactamente 6 ints (D102..D107)
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

Reglas globales del schema v2:
- **Tipos estrictos**: `StrictBool`, `StrictInt` en todos los campos (no se aceptan coerciones de string → int). `ts: datetime` (no `str`).
- **`extra='forbid'`** en todos los modelos (rechaza campos desconocidos).
- **`Field(default_factory=list)`** en todas las listas; ningún default mutable.
- **Longitudes fijas validadas**: `secciones=112`, `cercha_salidas=160`, `salidas_wr.raw_words=10`, `horarios.raw_words=28`, `horarios.tramos=12`, `plc_reloj.raw_words=7`, `reset_temporizado.dm_raw_words=6`.
- **Constantes endurecidas con `Literal`**: `max_reintentos=Literal[3]`, `physical_io_confirmed=Literal[False]` (impide marcar una salida como confirmada mientras siga `pending_cio_map`).
- **Status sin `'absent'`**: en v2 todos los bloques siempre se intentan → `Literal['ok', 'failed']` solamente.
- **`fins_ok` coherente**: `fins_ok = all(block.status == 'ok' for block in read_status.values())`.
- **Coherencia bloque ↔ payload**: si `status='ok'`, la sección correspondiente del payload no puede ser `None` y debe cumplir su longitud. Si `status='failed'`, esa sección debe ser `None` (o vacía controlada para `secciones`).

```python
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel, ConfigDict, Field, StrictBool, StrictInt,
    model_validator,
)

READ_BLOCKS_V2 = (
    'secciones', 'modo', 'fotocelula', 'reloj', 'horarios', 'diagnostico',
    'reset_temporizado', 'hmi_original', 'reloj_ar', 'salidas_wr',
)

# --- helpers de longitud ---
FixedLen10 = Annotated[list[StrictInt], Field(min_length=10, max_length=10)]
FixedLen6  = Annotated[list[StrictInt], Field(min_length=6,  max_length=6)]
FixedLen7  = Annotated[list[StrictInt], Field(min_length=7,  max_length=7)]
FixedLen28 = Annotated[list[StrictInt], Field(min_length=28, max_length=28)]

# --- bloques ---
class ReadBlockStatus(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['ok', 'failed']        # 'absent' eliminado en v2
    error: str | None = None

class SeccionPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: StrictInt                          # 1..112 (ver §6 Indexación)
    automatico_calculado: StrictBool
    manual_activo: StrictBool
    salida_interna: StrictBool
    salida_wr: StrictBool | None = None    # None si bloque salidas_wr falló

class TramoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tramo: StrictInt                       # 1..12
    inicio_hora: StrictInt | None
    inicio_minuto: StrictInt | None
    fin_hora: StrictInt
    fin_minuto: StrictInt
    inicio_raw: list[StrictInt] | None = None
    fin_raw: list[StrictInt] = Field(default_factory=list)
    source: dict[str, str] = Field(default_factory=dict)

class HorariosPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw_words: FixedLen28
    tramos: Annotated[list[TramoPayload], Field(min_length=12, max_length=12)]

class ModoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    modfunalu: StrictInt
    modo_label: Literal['horarios', 'fotocelula', 'ambos', 'desconocido']

class FotocelulaPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    entrada_raw: StrictBool
    entrada_raw_source: Literal['W25.00']
    mem_fun: StrictBool
    mem_fun_source: Literal['H100.00']
    filtrada_activa: StrictBool
    filtrada_source: Literal['H100.01']
    temporizador_activacion_s: StrictInt
    temporizador_desactivacion_s: StrictInt
    retardo_activacion_s: StrictInt
    retardo_desactivacion_s: StrictInt

class RelojDecoded(BaseModel):
    model_config = ConfigDict(extra='forbid')
    segundo: StrictInt; minuto: StrictInt; hora: StrictInt
    dia: StrictInt; mes: StrictInt; anio: StrictInt; dia_semana: StrictInt

class RelojPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw_words: FixedLen7
    encoding: Literal['binary', 'bcd']
    decoded: RelojDecoded

class DiagnosticoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cycle_time_error: StrictBool
    low_battery: StrictBool
    io_verify_error: StrictBool

class ResetSubPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    activo: StrictBool
    activo_source: Literal['W1.02']
    retardo_segundo_apagado_s: StrictInt
    temporizador_segundo_apagado_s: StrictInt
    contador_apagados: StrictInt
    max_reintentos: Literal[3] = 3         # constante endurecida

class ResetTemporizadoPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    w1_raw: StrictInt
    dm_raw_words: FixedLen6                # D102..D107
    horario_global_activo: StrictBool
    horario_global_activo_source: Literal['W1.01']
    reset: ResetSubPayload

class HmiOriginalPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    indice_seccion: StrictInt              # índice PLC raw D1008 (ver §6)
    indice_anterior: StrictInt
    automatico_seccion_seleccionada: StrictBool
    manual_seccion_seleccionada: StrictBool
    orden_transferencia_comun: StrictBool
    indicacion_activacion_alumbrado_seccion: StrictBool
    h10_raw: StrictInt

class RelojArRaw(BaseModel):
    model_config = ConfigDict(extra='forbid')
    A351_minsegplc: StrictInt
    A352_diahorplc: StrictInt
    A353_anomesplc: StrictInt

class RelojArDecoded(BaseModel):
    model_config = ConfigDict(extra='forbid')
    minuto: StrictInt; segundo: StrictInt
    dia: StrictInt; hora: StrictInt
    anio: StrictInt; mes: StrictInt

class RelojArPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw: RelojArRaw
    decoded: RelojArDecoded
    encoding: Literal['bcd_packed_channel']

class CerchaSalidaPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: StrictInt                                  # 1..160
    activa: StrictBool
    source: str                                    # 'W<word>.<bit>'
    physical_io_confirmed: Literal[False] = False  # endurecido: pending_cio_map

class SalidasWrPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw_words: FixedLen10
    cercha_salidas: Annotated[list[CerchaSalidaPayload], Field(min_length=160, max_length=160)]
    physical_io_mapping_status: Literal['pending_cio_map']

class LecturaPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[2]
    ts: datetime
    fins_ok: StrictBool
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

    # --- validadores semánticos ---

    @model_validator(mode='after')
    def _check_read_status_keys(self) -> 'LecturaPayload':
        expected = set(READ_BLOCKS_V2)
        actual = set(self.read_status.keys())
        if actual != expected:
            raise ValueError(
                f"read_status v2 requiere exactamente {sorted(expected)}, recibido {sorted(actual)}"
            )
        return self

    @model_validator(mode='after')
    def _check_fins_ok_consistency(self) -> 'LecturaPayload':
        all_ok = all(s.status == 'ok' for s in self.read_status.values())
        if self.fins_ok != all_ok:
            raise ValueError("fins_ok debe ser True si y solo si los 10 bloques tienen status='ok'")
        if self.fins_ok and self.fins_error is not None:
            raise ValueError("fins_ok=True requiere fins_error=None")
        return self

    @model_validator(mode='after')
    def _check_block_payload_coherence(self) -> 'LecturaPayload':
        def is_ok(block: str) -> bool:
            return self.read_status[block].status == 'ok'

        # secciones: si ok → exactamente 112 ids únicos 1..112
        if is_ok('secciones'):
            if len(self.secciones) != 112:
                raise ValueError(f"secciones ok requiere 112 entradas, hay {len(self.secciones)}")
            ids = sorted(s.id for s in self.secciones)
            if ids != list(range(1, 113)):
                raise ValueError("secciones ok requiere ids exactamente 1..112")
        else:
            if self.secciones:
                raise ValueError("secciones failed no acepta entradas")

        # caso especial: secciones ok + salidas_wr failed → salida_wr debe ser None en cada sección
        if is_ok('secciones') and not is_ok('salidas_wr'):
            if any(s.salida_wr is not None for s in self.secciones):
                raise ValueError("salidas_wr failed: cada seccion.salida_wr debe ser None")

        # bloques 1:1 con payload section
        pairs = (
            ('modo', self.modo), ('fotocelula', self.fotocelula),
            ('reloj', self.plc_reloj), ('horarios', self.horarios),
            ('diagnostico', self.diagnostico),
            ('reset_temporizado', self.reset_temporizado),
            ('hmi_original', self.hmi_original), ('reloj_ar', self.reloj_ar),
            ('salidas_wr', self.salidas_wr),
        )
        for block, payload in pairs:
            if is_ok(block) and payload is None:
                raise ValueError(f"bloque {block} ok requiere payload presente")
            if not is_ok(block) and payload is not None:
                raise ValueError(f"bloque {block} failed no acepta payload (debe ser None)")

        # salidas_wr ok: cercha_salidas ids exactamente 1..160
        if is_ok('salidas_wr'):
            cids = sorted(c.id for c in self.salidas_wr.cercha_salidas)
            if cids != list(range(1, 161)):
                raise ValueError("salidas_wr ok requiere cercha_salidas ids 1..160")

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

### 5.2 `horario_tramo` — ampliación no destructiva, sin backfill

**Estado actual:** `inicio_raw` y `fin_raw` son **`INTEGER`** (un solo int por fila), no JSON arrays. Además, el mapeo v1 era provisional/incorrecto (`listener.py` lo marca como `PENDIENTE P1`). Los valores históricos en esas columnas no son una representación fiable del raw real de la palabra DM.

**Decisión:** preservar las columnas legacy intactas (no se tocan, no se migran), y añadir **columnas v2 nuevas** que conviven con las legacy:

| Columna | Tipo | Nullable | Origen v2 |
|---|---|---|---|
| `inicio_raw` | INTEGER (legacy) | SÍ | INTACTA — datos v1; NULL para filas v2 |
| `fin_raw` | INTEGER (legacy) | SÍ | INTACTA — datos v1; NULL para filas v2 |
| `inicio_raw_words` | TEXT (JSON) | SÍ | NUEVA — lista de ints (o NULL para tramos 3-12) |
| `fin_raw_words` | TEXT (JSON) | SÍ | NUEVA — lista de ints (siempre presente en v2) |
| `source_json` | TEXT (JSON) | SÍ | NUEVA — dict `{'fin_hora':'D3632', ...}` |
| `inicio_hora` | INTEGER | SÍ | NUEVA — None para tramos 3-12 |
| `inicio_minuto` | INTEGER | SÍ | NUEVA — None para tramos 3-12 |
| `fin_hora` | INTEGER | SÍ | NUEVA — siempre presente en v2 |
| `fin_minuto` | INTEGER | SÍ | NUEVA — siempre presente en v2 |

**Nada de backfill** desde `inicio_raw`/`fin_raw` legacy hacia las columnas decodificadas v2: el dato origen no es fiable. Las filas v1 históricas mantienen sus dos enteros provisionales en las columnas legacy; las columnas v2 quedan NULL para esas filas. Filas v2 nuevas llevan las columnas v2 pobladas y las legacy NULL.

No se usa `server_default='0'` en ninguna columna nueva: falsearía la lectura histórica y desactivaría la convención "NULL = no aplicable / no v2".

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

### 5.4 Migración Alembic (`alembic/versions/20260524_0003_v2_semantic_layer.py`)

Batch mode obligatorio para SQLite (no soporta ALTER COLUMN directo). **Sin backfill** de columnas v2 (ver §5.2).

```python
def upgrade():
    with op.batch_alter_table('seccion_estado') as batch:
        batch.alter_column('automatico',     new_column_name='automatico_calculado')
        batch.alter_column('manual',         new_column_name='manual_activo')
        batch.alter_column('horario_activo', new_column_name='salida_interna')
        batch.add_column(sa.Column('salida_wr', sa.Boolean(), nullable=True))

    with op.batch_alter_table('horario_tramo') as batch:
        # NO se tocan inicio_raw / fin_raw (INTEGER legacy v1).
        # Nuevas columnas v2, todas nullable, sin server_default:
        batch.add_column(sa.Column('inicio_raw_words', sa.Text(),    nullable=True))  # JSON
        batch.add_column(sa.Column('fin_raw_words',    sa.Text(),    nullable=True))  # JSON
        batch.add_column(sa.Column('source_json',      sa.Text(),    nullable=True))  # JSON
        batch.add_column(sa.Column('inicio_hora',      sa.Integer(), nullable=True))
        batch.add_column(sa.Column('inicio_minuto',    sa.Integer(), nullable=True))
        batch.add_column(sa.Column('fin_hora',         sa.Integer(), nullable=True))
        batch.add_column(sa.Column('fin_minuto',       sa.Integer(), nullable=True))

    # Tablas nuevas (1:1 con ciclo)
    op.create_table('fotocelula_state',        ...)
    op.create_table('reset_temporizado_state', ...)
    op.create_table('hmi_original_state',      ...)
    op.create_table('reloj_ar_state',          ...)
    op.create_table('salidas_wr_state',        ...)


def downgrade():
    op.drop_table('salidas_wr_state')
    op.drop_table('reloj_ar_state')
    op.drop_table('hmi_original_state')
    op.drop_table('reset_temporizado_state')
    op.drop_table('fotocelula_state')

    with op.batch_alter_table('horario_tramo') as batch:
        for col in ('fin_minuto', 'fin_hora', 'inicio_minuto', 'inicio_hora',
                    'source_json', 'fin_raw_words', 'inicio_raw_words'):
            batch.drop_column(col)

    with op.batch_alter_table('seccion_estado') as batch:
        batch.drop_column('salida_wr')
        batch.alter_column('salida_interna',       new_column_name='horario_activo')
        batch.alter_column('manual_activo',        new_column_name='manual')
        batch.alter_column('automatico_calculado', new_column_name='automatico')
```

La migración es puramente estructural. La validación funcional ocurre en el primer ciclo v2 que escriba el subscriber, donde Pydantic rechazaría cualquier inconsistencia antes de tocar la base de datos.

---

## 6. Indexación (regla v2 explícita)

Para evitar ambigüedad entre índices PLC raw e identificadores del payload:

```text
secciones[i].id           es 1-based: 1..112
cercha_salidas[j].id      es 1-based: 1..160
tramos[t].tramo           es 1-based: 1..12
hmi_original.indice_seccion  CONSERVA el valor raw PLC (D1008), tal cual.
hmi_original.indice_anterior CONSERVA el valor raw PLC (D1009), tal cual.

Equivalencia para resolver la sección seleccionada por la HMI:
    seccion.id == hmi_original.indice_seccion + 1
    (D1008 es 0-based porque el ladder lo usa como subíndice de bit en
     H11.00[D1008], H18.00[D1008].)
```

Esta regla queda como contrato implícito del schema v2. No se añade un campo `plc_index` a `SeccionPayload` (se considera bloat: el cálculo es trivial y la regla está documentada aquí). Si en el futuro aparece necesidad de exponer `plc_index` explícito a consumidores externos, es un campo añadido sin romper compatibilidad.

---

## 7. Mapeo CIO físico — PENDIENTE explícito

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

## 8. Listener `subscriber/listener.py` — cambios

- Sustituir referencias `s.automatico`, `s.manual`, `s.horario_activo` por los nombres v2 (`automatico_calculado`, `manual_activo`, `salida_interna`)
- Escribir `salida_wr` en `seccion_estado` desde `secciones[i].salida_wr`
- Para `horario_tramo` (filas v2 nuevas):
  - **NO escribir** las columnas legacy `inicio_raw` / `fin_raw` (quedan NULL en filas v2)
  - Escribir las columnas v2: `inicio_raw_words` y `fin_raw_words` como JSON (`json.dumps([...])`), `source_json` igual, y los 4 enteros `inicio_hora`/`inicio_minuto`/`fin_hora`/`fin_minuto` (con NULL en `inicio_*` para tramos 3-12)
  - Eliminar el comentario PENDIENTE P1
- Añadir inserts a las 5 tablas nuevas: `fotocelula_state`, `reset_temporizado_state`, `hmi_original_state`, `reloj_ar_state`, `salidas_wr_state` (con `cercha_salidas` y `raw_words` serializados a JSON)

---

## 9. API `schemas/lectura.py`

Actualizar response models para reflejar campos v2. Los renombrados de `seccion_estado` se propagan automáticamente si Pydantic usa `from_attributes=True` contra el modelo SQLAlchemy actualizado. Para las nuevas tablas, definir response models nuevos que la API pueda exponer en endpoints por ciclo (`/ciclos/{id}/fotocelula`, `/ciclos/{id}/salidas_wr`, etc., scope a definir en el plan de implementación).

---

## 10. Tests

### 10.1 `tests/test_decoders.py` (NUEVO)

- `words()`: extrae `parse_words_to_int_list(response['data'])` correctamente; rechaza dict sin `data`
- `get_bit`: extremos (bit 0, bit 15) y bits intermedios
- `extract_section_bits`: idénticos a los 8 casos actuales de `test_poller.py`
- `decode_u32_low_high`: básico + valores grandes (high=0xFFFF)
- `decode_i32_low_high`: positivos, negativo (high con MSB), borde ±2^31
- `bcd_byte_to_int`: 0x00→0, 0x09→9, 0x10→10, 0x99→99; **0x0A, 0xAB, 0xFF → ValueError** (cobertura explícita del rechazo de nibbles > 9)
- `decode_modo_label`: 0→horarios, 1→fotocelula, 2→ambos, 99→desconocido
- `decode_ar_clock`: caso conocido manual + validación de keys; caso con AR351=0x9999 (no-BCD) → ValueError
- `decode_clock_dm`: encoding='binary' y encoding='bcd' (estructura, no validez de valores)
- `decode_schedule_tramos`: tramo 1 con inicio+fin (source incluye D1000/D1001 y D1002/D1003), tramo 5 solo fin (inicio_* = None, source solo fin_*), longitud total = 12 tramos
- `decode_cercha_salidas`: bit 0 → cercha 1 source 'W4.00'; bit 111 → cercha 112 source 'W10.15'; bit 112 → cercha 113 source 'W11.00'; bit 159 → cercha 160 source 'W13.15'; longitud total = 160; `physical_io_confirmed=False` para los 160

### 10.2 `tests/test_poller.py` (ACTUALIZAR)

- Actualizar fixtures FINS para incluir las nuevas lecturas (W1, H10, AR351..AR353, D102..D115, D1008..D1009, W4..W13)
- Cubrir los 10 bloques v2 individualmente (status 'ok' por bloque)
- Cubrir fallos parciales: un bloque falla, los demás se conservan
- `build_payload`: validar contra `LecturaPayload` (parseo Pydantic) en cada test
- Test específico de que `salida_wr` en cada sección refleja `cercha_salidas[id-1].activa` cuando `salidas_wr` ok
- Test específico: si `salidas_wr` falla y `secciones` ok → cada `seccion.salida_wr is None`
- Test específico de que `read_status` contiene exactamente los 10 nombres v2

### 10.3 `tests/test_payload_schema.py` (ACTUALIZAR)

Coverage de los validadores semánticos nuevos:
- Mensaje con `schema_version=1` → ValidationError (no acepta v1)
- `read_status` con 9 bloques o con un nombre v1 ajeno → ValidationError
- `fins_ok=True` pero un bloque con `status='failed'` → ValidationError
- `fins_ok=True` con `fins_error` no-None → ValidationError
- `secciones` con 111 entradas y bloque ok → ValidationError
- `secciones` ids no contiguos 1..112 → ValidationError
- `salidas_wr` failed con `secciones[0].salida_wr=True` → ValidationError
- `cercha_salidas` con 159 entradas → ValidationError
- `cercha_salidas[i].physical_io_confirmed=True` → ValidationError (Literal[False])
- `reset_temporizado.reset.max_reintentos=5` → ValidationError (Literal[3])
- Bloque `fotocelula` ok con `fotocelula=None` → ValidationError
- Bloque `fotocelula` failed con `fotocelula` poblado → ValidationError
- `salidas_wr.raw_words` con 11 ints → ValidationError
- `horarios.raw_words` con 27 ints → ValidationError
- `horarios.tramos` con 11 entradas → ValidationError
- `plc_reloj.raw_words` con 6 ints → ValidationError
- `reset_temporizado.dm_raw_words` con 5 ints → ValidationError

### 10.4 `tests/test_indexacion.py` (NUEVO)

- Regla del §6: dado `hmi_original.indice_seccion = D1008`, la sección seleccionada cumple `seccion.id == indice_seccion + 1` (cubrir D1008=0 → id=1, D1008=111 → id=112)

---

## 11. Despliegue

1. Detener publisher RPi
2. Detener subscriber/API Lenovo
3. Backup SQLite: `cp alumbrado.db alumbrado.db.bak.$(date +%Y%m%d-%H%M%S)`
4. Actualizar código en ambos nodos (git pull)
5. Ejecutar migración Alembic: `alembic upgrade head` (puramente estructural; sin backfill)
6. Arrancar subscriber/API Lenovo (verificar que arranca sin errores Pydantic)
7. Arrancar publisher RPi
8. Verificación primer ciclo: `read_status` con los 10 bloques v2 en `status='ok'`, modo_label coherente con D116, `cercha_salidas[0].source == 'W4.00'`

---

## 12. Fuera de alcance (deuda técnica documentada)

- Escrituras al PLC (read-only mode TFG)
- Mapeo CIO/bornera físico (`pending_cio_map` — todas las 160 cerchas con `physical_io_confirmed: False`)
- Cambios en `fins/` (transporte UDP read-only intacto)
- Compatibilidad retroactiva con schema_version=1 (clean break)
- Lectura de cycle-time-value (AR264/AR265 UDINT) — sólo se conservan los bits de error AR401/AR402
- Validación empírica del orden high/low byte en `decode_ar_clock` y del encoding real de D500..D506 (binary vs bcd): pendiente de smoke con PLC real antes de cerrar valores como fijos
- Tabla detalle por cercha individual (alternativa a JSON column en `salidas_wr_state`) — añadir si surge necesidad analítica
