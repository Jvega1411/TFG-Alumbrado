# Plan B — FINS Reader + MQTT Publisher (RPi)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Leer todas las variables del PLC cada 10s y publicarlas via MQTT al broker Mosquitto del Lenovo, publicando solo cuando cambia algún valor o cada 5 minutos (heartbeat).

**Architecture:** `acquisition/poller.py` añade `read_all_variables()` y `build_payload()`. `acquisition/publisher.py` (nuevo) gestiona la detección de cambios, el cliente paho-mqtt y el loop principal. `config/settings.py` recibe los parámetros MQTT.

**Tech Stack:** Python 3.12, paho-mqtt, fins/client.py (ya implementado y testeado), config/settings.py (ya implementado).

**Invariante obligatoria:** Nunca usar `datetime.utcnow()`. Siempre `datetime.now(tz=timezone.utc)`.

---

## File Map

| Fichero | Acción | Responsabilidad |
|---|---|---|
| `config/settings.py` | Modificar | Añadir MQTT_* y HEARTBEAT_INTERVAL_S, actualizar ACQUISITION_INTERVAL_S |
| `acquisition/poller.py` | Modificar | Añadir read_all_variables() y build_payload() / build_error_payload() |
| `acquisition/publisher.py` | Crear | Detección de cambios, cliente MQTT, run_publisher() |
| `tests/test_settings.py` | Modificar | Tests de los nuevos atributos MQTT |
| `tests/test_poller.py` | Modificar | Tests de read_all_variables, build_payload, build_error_payload |
| `tests/test_publisher.py` | Crear | Tests de _payloads_equal, run_publisher con mocks |

---

## Task 1: Config — parámetros MQTT

**Files:**
- Modify: `config/settings.py`
- Modify: `tests/test_settings.py`

- [ ] **Step 1: Añadir tests de los nuevos atributos**

Al final de `TestConfigValidation` en `tests/test_settings.py`:

```python
def test_mqtt_broker_host_default_is_empty(self):
    # Default vacío: la subred enlace IT está pendiente de confirmar (PENDIENTE P5)
    # MQTT_BROKER_HOST debe configurarse explícitamente en .env; arrancar sin él falla validate()
    assert Config.MQTT_BROKER_HOST == ''

def test_validate_publisher_fails_if_mqtt_broker_host_empty(self):
    original = Config.MQTT_BROKER_HOST
    try:
        Config.MQTT_BROKER_HOST = ''
        with pytest.raises(ValueError, match="MQTT_BROKER_HOST"):
            Config.validate_publisher()
    finally:
        Config.MQTT_BROKER_HOST = original

def test_validate_api_passes_without_mqtt_broker_host(self):
    original = Config.MQTT_BROKER_HOST
    try:
        Config.MQTT_BROKER_HOST = ''
        Config.validate_api()  # no debe lanzar aunque MQTT_BROKER_HOST esté vacío
    finally:
        Config.MQTT_BROKER_HOST = original

def test_validate_subscriber_does_not_require_fins_config(self):
    """El subscriber corre en nodo IT: requiere MQTT+DB, pero no parámetros FINS/PLC."""
    original_host = Config.MQTT_BROKER_HOST
    original_plc_ip = Config.PLC_IP
    try:
        Config.MQTT_BROKER_HOST = '127.0.0.1'
        Config.PLC_IP = 'ip-plc-invalida-para-it'
        Config.validate_subscriber()
    finally:
        Config.MQTT_BROKER_HOST = original_host
        Config.PLC_IP = original_plc_ip

def test_mqtt_broker_port_default(self):
    assert Config.MQTT_BROKER_PORT == 1883

def test_mqtt_topic_default(self):
    assert Config.MQTT_TOPIC == 'alumbrado/estado'

def test_mqtt_client_id_default(self):
    assert Config.MQTT_CLIENT_ID == 'alumbrado-publisher'

def test_heartbeat_interval_default(self):
    assert Config.HEARTBEAT_INTERVAL_S == 300.0

def test_acquisition_interval_default_is_10(self):
    assert Config.ACQUISITION_INTERVAL_S == 10.0

# NOTA: test_db_and_acquisition_defaults en el archivo existente aún aserta == 30.0.
# Cambiarlo a == 10.0 (o eliminar esa línea) al implementar este Task.

def test_api_host_default_is_localhost(self):
    # Default 127.0.0.1: no exponer en todas las interfaces sin configuración explícita
    assert Config.API_HOST == '127.0.0.1'

def test_api_port_default(self):
    assert Config.API_PORT == 8000

def test_db_auto_create_default_is_false(self):
    # False por defecto: producción usa alembic upgrade head, no create_all automático
    assert Config.DB_AUTO_CREATE is False
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_settings.py::TestConfigValidation::test_mqtt_broker_host_default -v
```

Expected: `FAILED` con `AttributeError`

- [ ] **Step 3: Añadir atributos a Config**

En `config/settings.py`, dentro de la clase `Config`, después de `ACQUISITION_INTERVAL_S`:

```python
# MQTT — MQTT_BROKER_HOST intencionalmente vacío: la subred enlace no está confirmada (PENDIENTE P5)
# Configurar en .env antes de arrancar. validate() falla si está vacío.
MQTT_BROKER_HOST: str  = os.getenv('MQTT_BROKER_HOST', '')
MQTT_BROKER_PORT: int  = int(os.getenv('MQTT_BROKER_PORT', '1883'))
MQTT_TOPIC: str        = os.getenv('MQTT_TOPIC', 'alumbrado/estado')
MQTT_CLIENT_ID: str    = os.getenv('MQTT_CLIENT_ID', 'alumbrado-publisher')
HEARTBEAT_INTERVAL_S: float = float(os.getenv('HEARTBEAT_INTERVAL_S', '300.0'))

# FastAPI — default 127.0.0.1 para no exponer en todas las interfaces sin configuración explícita
API_HOST: str = os.getenv('API_HOST', '127.0.0.1')
API_PORT: int = int(os.getenv('API_PORT', '8000'))

# BD — False en producción: usar `alembic upgrade head` en vez de create_all automático
DB_AUTO_CREATE: bool = os.getenv('DB_AUTO_CREATE', 'false').lower() == 'true'
```

Cambiar el default de `ACQUISITION_INTERVAL_S` de `'30.0'` a `'10.0'`:

```python
ACQUISITION_INTERVAL_S: float = float(os.getenv('ACQUISITION_INTERVAL_S', '10.0'))
```

**NO modificar `validate()` existente.** Añadir helpers privados y tres classmethods nuevos después del `validate()` existente. Cada proceso llama al método de su rol antes de arrancar.

Regla de separación OT/IT:
- `validate_publisher()` es el único método que valida FINS/PLC, porque corre en RPi-OT.
- `validate_subscriber()` valida solo MQTT+DB, porque corre en Nodo-IT y no debe depender de configuración FINS/PLC.
- `validate_api()` valida solo API+DB, porque FastAPI tampoco necesita MQTT ni FINS.

```python
@classmethod
def _validate_db(cls) -> None:
    if not cls.DB_ESTADOS_URL.strip():
        raise ValueError("DB_ESTADOS_URL no puede estar vacia")

@classmethod
def _validate_mqtt(cls) -> None:
    if not cls.MQTT_BROKER_HOST.strip():
        raise ValueError("MQTT_BROKER_HOST no puede estar vacio — configurar en .env")
    if not (1 <= cls.MQTT_BROKER_PORT <= 65535):
        raise ValueError(f"MQTT_BROKER_PORT fuera de rango: {cls.MQTT_BROKER_PORT}")
    if not cls.MQTT_TOPIC.strip():
        raise ValueError("MQTT_TOPIC no puede estar vacio")
    if not cls.MQTT_CLIENT_ID.strip():
        raise ValueError("MQTT_CLIENT_ID no puede estar vacio")
    if cls.HEARTBEAT_INTERVAL_S <= 0:
        raise ValueError(f"HEARTBEAT_INTERVAL_S debe ser positivo: {cls.HEARTBEAT_INTERVAL_S}")

@classmethod
def validate_api(cls) -> None:
    """Validación para el proceso FastAPI (nodo IT). No requiere MQTT ni FINS."""
    cls._validate_db()
    if not cls.API_HOST.strip():
        raise ValueError("API_HOST no puede estar vacio")
    if not (1 <= cls.API_PORT <= 65535):
        raise ValueError(f"API_PORT fuera de rango: {cls.API_PORT}")

@classmethod
def validate_publisher(cls) -> None:
    """Validación para el proceso FINS publisher (nodo OT). Requiere FINS + MQTT."""
    cls.validate()  # validaciones FINS/UDP existentes
    cls._validate_mqtt()

@classmethod
def validate_subscriber(cls) -> None:
    """Validación para el proceso MQTT subscriber (nodo IT). Requiere MQTT + DB, no FINS."""
    cls._validate_db()
    cls._validate_mqtt()
```

- [ ] **Step 4: Verificar que todos los tests de settings pasan**

```
pytest tests/test_settings.py -v
```

Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add config/settings.py tests/test_settings.py
git commit -m "feat(config): añadir parámetros MQTT y HEARTBEAT_INTERVAL_S"
```

---

## Task 2: read_all_variables() en poller.py

**Files:**
- Modify: `acquisition/poller.py`
- Modify: `tests/test_poller.py`

**Contexto:** `fins/client.py` ya tiene: `read_dm_range(start, count)`, `read_h_range(start, count)`, `read_w_range(start, count)`, `read_ar_range(start, count)`. Todos devuelven `{'data': bytes, 'word_count': int, ...}`. `fins/frame.py` tiene `parse_words_to_int_list(data: bytes) -> list[int]` y la excepción base `FINSError`.

- [ ] **Step 1: Escribir tests de read_all_variables**

Añadir al final de `tests/test_poller.py`:

```python
from unittest.mock import Mock
from acquisition.poller import read_all_variables
from fins.frame import parse_words_to_int_list


def _make_words_bytes(words: list) -> bytes:
    """Convierte lista de ints a bytes big-endian (2 bytes por word)."""
    result = b''
    for w in words:
        result += bytes([(w >> 8) & 0xFF, w & 0xFF])
    return result


def _make_fins_response(words: list) -> dict:
    data = _make_words_bytes(words)
    return {'success': True, 'mres': 0, 'sres': 0, 'data': data, 'word_count': len(words)}


class TestReadAllVariables:

    def _make_client(self):
        """Cliente mock con todas las respuestas en cero."""
        client = Mock()
        client.read_h_range.return_value = _make_fins_response([0] * 21)   # H11-H31
        client.read_dm_range.side_effect = lambda start, count: _make_fins_response([0] * count)
        client.read_w_range.return_value = _make_fins_response([0])        # W25
        client.read_ar_range.return_value = _make_fins_response([0])       # A401/A402
        return client

    def test_returns_112_secciones(self):
        result = read_all_variables(self._make_client())
        assert len(result['secciones']) == 112

    def test_seccion_ids_are_1_to_112(self):
        result = read_all_variables(self._make_client())
        ids = [s['id'] for s in result['secciones']]
        assert ids == list(range(1, 113))

    def test_all_zeros_returns_false_states(self):
        result = read_all_variables(self._make_client())
        for s in result['secciones']:
            assert s['automatico'] is False
            assert s['manual'] is False
            assert s['horario_activo'] is False

    def test_h11_bit0_sets_seccion1_automatico(self):
        client = self._make_client()
        words_h = [0] * 21
        words_h[0] = 0x0001  # H11 bit0 → seccion 1 automatico
        client.read_h_range.return_value = _make_fins_response(words_h)
        result = read_all_variables(client)
        assert result['secciones'][0]['automatico'] is True
        assert result['secciones'][0]['manual'] is False

    def test_h18_bit0_sets_seccion1_manual(self):
        client = self._make_client()
        words_h = [0] * 21
        words_h[7] = 0x0001  # H18 bit0 → seccion 1 manual (group_offset=7)
        client.read_h_range.return_value = _make_fins_response(words_h)
        result = read_all_variables(client)
        assert result['secciones'][0]['manual'] is True

    def test_d116_modfunalu(self):
        client = self._make_client()
        client.read_dm_range.side_effect = lambda start, count: (
            _make_fins_response([2]) if start == 116
            else _make_fins_response([0] * count)
        )
        result = read_all_variables(client)
        assert result['modfunalu'] == 2

    def test_w25_bit0_fotocelula_entrada(self):
        client = self._make_client()
        client.read_w_range.return_value = _make_fins_response([0x0001])
        result = read_all_variables(client)
        assert result['fotocelula_entrada'] is True

    def test_h100_bit0_fotocelula_mem_fun(self):
        client = self._make_client()
        # H100 está en el mismo read_h_range pero es una llamada separada
        # read_h_range se llama con (11, 21) para secciones y (100, 1) para fotocelula
        call_count = [0]
        def h_range_side_effect(start, count):
            call_count[0] += 1
            if start == 100:
                return _make_fins_response([0x0001])  # bit0=1
            return _make_fins_response([0] * count)
        client.read_h_range.side_effect = h_range_side_effect
        result = read_all_variables(client)
        assert result['fotocelula_mem_fun'] is True
        assert result['fotocelula_mem_act'] is False

    def test_a401_bit8_cycle_time_error(self):
        client = self._make_client()
        def ar_side_effect(start, count):
            if start == 401:
                return _make_fins_response([0x0100])  # bit8 = 1
            return _make_fins_response([0])
        client.read_ar_range.side_effect = ar_side_effect
        result = read_all_variables(client)
        assert result['cycle_time_error'] is True

    def test_a402_bit4_low_battery(self):
        client = self._make_client()
        def ar_side_effect(start, count):
            if start == 402:
                return _make_fins_response([0x0010])  # bit4 = 1
            return _make_fins_response([0])
        client.read_ar_range.side_effect = ar_side_effect
        result = read_all_variables(client)
        assert result['low_battery'] is True

    def test_a402_bit9_io_verify_error(self):
        client = self._make_client()
        def ar_side_effect(start, count):
            if start == 402:
                return _make_fins_response([0x0200])  # bit9 = 1
            return _make_fins_response([0])
        client.read_ar_range.side_effect = ar_side_effect
        result = read_all_variables(client)
        assert result['io_verify_error'] is True

    def test_reloj_plc_parsed(self):
        client = self._make_client()
        # D500-D506: seg=5, min=30, hora=8, dia=12, mes=5, anio=2026, diasem=2
        reloj = [5, 30, 8, 12, 5, 2026, 2]
        client.read_dm_range.side_effect = lambda start, count: (
            _make_fins_response(reloj) if start == 500
            else _make_fins_response([0] * count)
        )
        result = read_all_variables(client)
        assert result['plc_seg'] == 5
        assert result['plc_min'] == 30
        assert result['plc_hora'] == 8
        assert result['plc_anio'] == 2026
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_poller.py::TestReadAllVariables -v
```

Expected: `FAILED` con `ImportError: cannot import name 'read_all_variables'`

- [ ] **Step 3: Implementar read_all_variables() en acquisition/poller.py**

Añadir al final de `acquisition/poller.py` (después de `extract_section_bits`):

```python
from datetime import datetime, timezone
from fins.client import FINSClient


def read_all_variables(client: FINSClient) -> dict:
    """Lee todas las variables del PLC. Lanza FINSError/OSError si falla."""
    # H11-H31: 21 words — automaticos (offset 0), manuales (offset 7), memactsec (offset 14)
    result_h = client.read_h_range(11, 21)
    words_h = parse_words_to_int_list(result_h['data'])
    automaticos = extract_section_bits(words_h, 0)
    manuales    = extract_section_bits(words_h, 7)
    memactsec   = extract_section_bits(words_h, 14)

    # D116: modfunalu
    result_d116 = client.read_dm_range(116, 1)
    modfunalu = parse_words_to_int_list(result_d116['data'])[0]

    # W25: fotocelula_entrada (bit 0)
    result_w25 = client.read_w_range(25, 1)
    w25 = parse_words_to_int_list(result_w25['data'])[0]
    fotocelula_entrada = bool(w25 & 0x0001)

    # H100: fotocelula mem (bit0 = mem_fun, bit1 = mem_act)
    result_h100 = client.read_h_range(100, 1)
    h100 = parse_words_to_int_list(result_h100['data'])[0]
    fotocelula_mem_fun = bool(h100 & 0x0001)
    fotocelula_mem_act = bool((h100 >> 1) & 0x0001)

    # D500-D506: reloj PLC (7 words) — D500/D505 intercambiados en PDF, usar orden real
    result_reloj = client.read_dm_range(500, 7)
    reloj = parse_words_to_int_list(result_reloj['data'])
    # reloj[0]=seg(D500), [1]=min(D501), [2]=hora(D502), [3]=dia(D503), [4]=mes(D504), [5]=anio(D505), [6]=diasem(D506)

    # D1000-D1007: horarios tramos raw (8 words)
    result_hor12 = client.read_dm_range(1000, 8)
    horarios_raw_1_2 = parse_words_to_int_list(result_hor12['data'])

    # D3632-D3651: horarios fin tramos raw (20 words)
    result_hor3_12 = client.read_dm_range(3632, 20)
    horarios_raw_3_12 = parse_words_to_int_list(result_hor3_12['data'])

    # A401: cycle_time_error (bit 8)
    result_a401 = client.read_ar_range(401, 1)
    a401 = parse_words_to_int_list(result_a401['data'])[0]
    cycle_time_error = bool((a401 >> 8) & 0x0001)

    # A402: low_battery (bit 4), io_verify_error (bit 9)
    result_a402 = client.read_ar_range(402, 1)
    a402 = parse_words_to_int_list(result_a402['data'])[0]
    low_battery    = bool((a402 >> 4) & 0x0001)
    io_verify_error = bool((a402 >> 9) & 0x0001)

    return {
        'secciones': [
            {
                'id': i + 1,
                'automatico':    automaticos[i],
                'manual':        manuales[i],
                'horario_activo': memactsec[i],
            }
            for i in range(112)
        ],
        'modfunalu': modfunalu,
        'fotocelula_entrada': fotocelula_entrada,
        'fotocelula_mem_fun': fotocelula_mem_fun,
        'fotocelula_mem_act': fotocelula_mem_act,
        'plc_seg':    reloj[0],
        'plc_min':    reloj[1],
        'plc_hora':   reloj[2],
        'plc_dia':    reloj[3],
        'plc_mes':    reloj[4],
        'plc_anio':   reloj[5],
        'plc_diasem': reloj[6],
        'horarios_raw': horarios_raw_1_2 + horarios_raw_3_12,
        'cycle_time_error': cycle_time_error,
        'low_battery':      low_battery,
        'io_verify_error':  io_verify_error,
    }
```

- [ ] **Step 4: Verificar que los tests pasan**

```
pytest tests/test_poller.py::TestReadAllVariables -v
```

Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add acquisition/poller.py tests/test_poller.py
git commit -m "feat(poller): añadir read_all_variables() con todas las variables PLC"
```

---

## Task 3: build_payload() y build_error_payload() en poller.py

**Files:**
- Modify: `acquisition/poller.py`
- Modify: `tests/test_poller.py`

- [ ] **Step 1: Escribir tests de build_payload**

Añadir al final de `tests/test_poller.py`:

```python
from datetime import datetime, timezone
from acquisition.poller import build_payload, build_error_payload


def _sample_variables() -> dict:
    return {
        'secciones': [{'id': i+1, 'automatico': False, 'manual': False, 'horario_activo': False} for i in range(112)],
        'modfunalu': 0,
        'fotocelula_entrada': False,
        'fotocelula_mem_fun': False,
        'fotocelula_mem_act': False,
        'plc_seg': 0, 'plc_min': 30, 'plc_hora': 8,
        'plc_dia': 12, 'plc_mes': 5, 'plc_anio': 2026, 'plc_diasem': 2,
        'horarios_raw': [0] * 28,
        'cycle_time_error': False,
        'low_battery': False,
        'io_verify_error': False,
    }


class TestBuildPayload:

    def test_fins_ok_true(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_payload(ts, _sample_variables())
        assert payload['fins_ok'] is True
        assert payload['fins_error'] is None

    def test_ts_is_iso_string(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_payload(ts, _sample_variables())
        assert isinstance(payload['ts'], str)
        assert '2026' in payload['ts']

    def test_has_112_secciones(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_payload(ts, _sample_variables())
        assert len(payload['secciones']) == 112

    def test_modfunalu_in_modo(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        vars_ = _sample_variables()
        vars_['modfunalu'] = 1
        payload = build_payload(ts, vars_)
        assert payload['modo']['modfunalu'] == 1

    def test_reloj_plc_hora(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        vars_ = _sample_variables()
        vars_['plc_hora'] = 14
        payload = build_payload(ts, vars_)
        assert payload['plc_reloj']['hora'] == 14

    def test_horarios_raw_words_length(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_payload(ts, _sample_variables())
        assert len(payload['horarios']['raw_words']) == 28

    def test_diagnostico_fields(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        vars_ = _sample_variables()
        vars_['low_battery'] = True
        payload = build_payload(ts, vars_)
        assert payload['diagnostico']['low_battery'] is True
        assert payload['diagnostico']['cycle_time_error'] is False


class TestBuildErrorPayload:

    def test_fins_ok_false(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_error_payload(ts, 'MRES=0x21 SRES=0x08')
        assert payload['fins_ok'] is False
        assert payload['fins_error'] == 'MRES=0x21 SRES=0x08'

    def test_has_ts(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_error_payload(ts, 'timeout')
        assert 'ts' in payload

    def test_no_secciones_key(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_error_payload(ts, 'timeout')
        assert 'secciones' not in payload
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_poller.py::TestBuildPayload tests/test_poller.py::TestBuildErrorPayload -v
```

Expected: `FAILED` con `ImportError`

- [ ] **Step 3: Implementar build_payload() y build_error_payload()**

Añadir al final de `acquisition/poller.py`:

```python
def build_payload(ts: datetime, variables: dict) -> dict:
    return {
        'ts': ts.isoformat(),
        'fins_ok': True,
        'fins_error': None,
        'plc_reloj': {
            'seg':    variables['plc_seg'],
            'min':    variables['plc_min'],
            'hora':   variables['plc_hora'],
            'dia':    variables['plc_dia'],
            'mes':    variables['plc_mes'],
            'anio':   variables['plc_anio'],
            'diasem': variables['plc_diasem'],
        },
        'modo': {
            'modfunalu':          variables['modfunalu'],
            'fotocelula_entrada': variables['fotocelula_entrada'],
            'fotocelula_mem_fun': variables['fotocelula_mem_fun'],
            'fotocelula_mem_act': variables['fotocelula_mem_act'],
        },
        'secciones': variables['secciones'],
        'horarios': {'raw_words': variables['horarios_raw']},
        'diagnostico': {
            'cycle_time_error': variables['cycle_time_error'],
            'low_battery':      variables['low_battery'],
            'io_verify_error':  variables['io_verify_error'],
        },
    }


def build_error_payload(ts: datetime, error: str) -> dict:
    return {
        'ts': ts.isoformat(),
        'fins_ok': False,
        'fins_error': error,
    }
```

- [ ] **Step 4: Verificar que todos los tests del poller pasan**

```
pytest tests/test_poller.py -v
```

Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add acquisition/poller.py tests/test_poller.py
git commit -m "feat(poller): añadir build_payload() y build_error_payload()"
```

---

## Task 4: acquisition/publisher.py — detección de cambios y loop MQTT

**Files:**
- Create: `acquisition/publisher.py`
- Create: `tests/test_publisher.py`

- [ ] **Step 1: Escribir tests de publisher**

Crear `tests/test_publisher.py`:

```python
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from acquisition.publisher import _payloads_equal, run_publisher


class TestPayloadsEqual:

    def _payload(self, modfunalu=0, sec1_auto=False) -> dict:
        secciones = [{'id': i+1, 'automatico': False, 'manual': False, 'horario_activo': False} for i in range(112)]
        secciones[0]['automatico'] = sec1_auto
        return {
            'ts': '2026-05-12T08:30:00+00:00',
            'fins_ok': True,
            'fins_error': None,
            'modo': {'modfunalu': modfunalu, 'fotocelula_entrada': False,
                     'fotocelula_mem_fun': False, 'fotocelula_mem_act': False},
            'secciones': secciones,
            'horarios': {'raw_words': [0] * 28},
            'diagnostico': {'cycle_time_error': False, 'low_battery': False, 'io_verify_error': False},
        }

    def test_equal_payloads_ignores_ts(self):
        a = self._payload()
        b = self._payload()
        b['ts'] = '2026-05-12T08:30:10+00:00'  # diferente timestamp
        assert _payloads_equal(a, b) is True

    def test_different_modfunalu_not_equal(self):
        a = self._payload(modfunalu=0)
        b = self._payload(modfunalu=1)
        assert _payloads_equal(a, b) is False

    def test_different_seccion_state_not_equal(self):
        a = self._payload(sec1_auto=False)
        b = self._payload(sec1_auto=True)
        assert _payloads_equal(a, b) is False

    def test_same_seccion_states_equal(self):
        a = self._payload(sec1_auto=True)
        b = self._payload(sec1_auto=True)
        b['ts'] = '2099-01-01T00:00:00+00:00'
        assert _payloads_equal(a, b) is True

    def test_error_payload_not_equal_to_ok(self):
        ok = self._payload()
        err = {'ts': '2026-05-12T08:30:00+00:00', 'fins_ok': False, 'fins_error': 'timeout'}
        assert _payloads_equal(ok, err) is False


class TestRunPublisher:
    # _make_mock_client eliminado — dead code. Los tests parchean read_all_variables directamente.

    def _base_vars(self):
        return {
            'secciones': [{'id': i+1, 'automatico': False, 'manual': False, 'horario_activo': False} for i in range(112)],
            'modfunalu': 0, 'fotocelula_entrada': False, 'fotocelula_mem_fun': False,
            'fotocelula_mem_act': False, 'plc_seg': 0, 'plc_min': 0, 'plc_hora': 0,
            'plc_dia': 1, 'plc_mes': 1, 'plc_anio': 2026, 'plc_diasem': 1,
            'horarios_raw': [0]*28, 'cycle_time_error': False,
            'low_battery': False, 'io_verify_error': False,
        }

    def _mock_fins(self):
        mock_fins = Mock()
        mock_fins.__enter__ = Mock(return_value=mock_fins)
        mock_fins.__exit__ = Mock(return_value=False)
        return mock_fins

    def test_publishes_on_first_run(self):
        mock_mqtt = Mock()

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()):
            run_publisher(max_cycles=1)

        mock_mqtt.publish.assert_called_once()

    def test_does_not_publish_when_unchanged(self):
        # publish() devuelve rc=0 e is_published()=True → last_payload se actualiza tras ciclo 1
        mock_msg_info = Mock()
        mock_msg_info.rc = 0  # mqtt.MQTT_ERR_SUCCESS
        mock_msg_info.is_published.return_value = True

        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = mock_msg_info

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()), \
             patch('acquisition.publisher.time.monotonic', return_value=0.0):
            run_publisher(max_cycles=2)

        # Ciclo 1 publica (last_payload=None). Ciclo 2 no (igual + sin heartbeat).
        assert mock_mqtt.publish.call_count == 1

    def test_publishes_on_fins_error(self):
        from fins.frame import FINSError

        mock_mqtt = Mock()

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', side_effect=FINSError('timeout')):
            run_publisher(max_cycles=1)

        assert mock_mqtt.publish.call_count == 1
        published_payload = json.loads(mock_mqtt.publish.call_args[0][1])
        assert published_payload['fins_ok'] is False

    def test_publish_failure_does_not_update_last_payload(self):
        """Si publish() devuelve rc!=0, last_payload no se actualiza y se reintenta en el siguiente ciclo."""
        mock_msg_info = Mock()
        mock_msg_info.rc = 4  # MQTT_ERR_NO_CONN — entrega fallida
        mock_msg_info.is_published.return_value = False

        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = mock_msg_info

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()), \
             patch('acquisition.publisher.time.monotonic', return_value=0.0):
            run_publisher(max_cycles=2)

        # Ambos ciclos publican porque rc!=0 impidió actualizar last_payload.
        assert mock_mqtt.publish.call_count == 2
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_publisher.py -v
```

Expected: `FAILED` con `ModuleNotFoundError: No module named 'acquisition.publisher'`

- [ ] **Step 3: Implementar acquisition/publisher.py**

Crear `acquisition/publisher.py`:

```python
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt

from acquisition.poller import build_error_payload, build_payload, read_all_variables
from config.settings import Config
from fins.client import FINSClient
from fins.frame import FINSError

logger = logging.getLogger(__name__)


def _payloads_equal(a: dict, b: dict) -> bool:
    """Compara dos payloads ignorando el campo 'ts'."""
    def _without_ts(d: dict) -> dict:
        return {k: v for k, v in d.items() if k != 'ts'}
    return _without_ts(a) == _without_ts(b)


def run_publisher(max_cycles: Optional[int] = None) -> None:
    """Loop principal del publisher.

    max_cycles: si se pasa un entero, detiene el loop tras ese número de ciclos.
    Solo para tests — en producción se omite (loop infinito).
    """
    Config.validate_publisher()

    mqtt_client = mqtt.Client(client_id=Config.MQTT_CLIENT_ID)
    mqtt_client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, keepalive=60)
    mqtt_client.loop_start()

    last_payload: Optional[dict] = None
    last_publish_time: float = 0.0
    cycle = 0

    with FINSClient() as fins:
        while max_cycles is None or cycle < max_cycles:
            now = datetime.now(tz=timezone.utc)
            try:
                variables = read_all_variables(fins)
                payload = build_payload(now, variables)
            except (FINSError, OSError, ValueError) as exc:
                payload = build_error_payload(now, str(exc))
                logger.warning("Fallo FINS: %s", exc)

            elapsed = time.monotonic() - last_publish_time
            should_publish = (
                last_payload is None
                or not _payloads_equal(payload, last_payload)
                or elapsed >= Config.HEARTBEAT_INTERVAL_S
            )

            if should_publish:
                msg_info = mqtt_client.publish(
                    Config.MQTT_TOPIC,
                    json.dumps(payload),
                    qos=1,
                )
                try:
                    msg_info.wait_for_publish(timeout=5.0)
                    if msg_info.rc == mqtt.MQTT_ERR_SUCCESS and msg_info.is_published():
                        last_payload = payload
                        last_publish_time = time.monotonic()
                        logger.info("MQTT publicado — fins_ok=%s", payload['fins_ok'])
                    else:
                        logger.warning("MQTT publish no confirmado: rc=%d is_published=%s",
                                       msg_info.rc, msg_info.is_published())
                except (ValueError, RuntimeError) as exc:
                    logger.warning("MQTT wait_for_publish error: %s", exc)

            cycle += 1
            if max_cycles is None:
                time.sleep(Config.ACQUISITION_INTERVAL_S)
```

- [ ] **Step 4: Verificar que todos los tests pasan**

```
pytest tests/test_publisher.py -v
```

Expected: todos PASSED

- [ ] **Step 5: Verificar suite completa**

```
pytest tests/ -v
```

Expected: todos PASSED

- [ ] **Step 6: Commit**

```bash
git add acquisition/publisher.py tests/test_publisher.py
git commit -m "feat(publisher): MQTT publisher con detección de cambios y heartbeat"
```

---

## Self-Review del plan B

- Spec B cubierto: read_all_variables (Task 2) ✅, build_payload (Task 3) ✅, change detection + heartbeat (Task 4) ✅, config MQTT (Task 1) ✅
- `read_ar_range` existe en fins/client.py (línea 71) ✅
- `datetime.now(tz=timezone.utc)` en publisher.py ✅
- Tipado compatible Python 3.9+: publisher usa `Optional[dict]`, no `dict | None` ✅
- Tests de publisher usan mock de FINSClient y mqtt.Client, sin UDP real ✅

### Correcciones aplicadas (auditoría 2026-05-12)

- **Fix 1:** `_validate_db()` usaba `cls.DB_URL` (no existe) → corregido a `cls.DB_ESTADOS_URL`
- **Fix 2:** `test_db_and_acquisition_defaults` aún aserta `== 30.0` → actualizar a `== 10.0` al implementar Task 1
- **Fix 3:** Los 4 tests de `TestRunPublisher` no mockeaban `Config.validate_publisher()` → añadido `patch('acquisition.publisher.Config.validate_publisher')` en todos
- **Fix 4:** `test_does_not_publish_when_unchanged` usaba `Mock()` sin `rc=0` → `last_payload` nunca se actualizaba → corregido con `mock_msg_info.rc = 0` e `is_published.return_value = True`
- **Fix 5:** `_make_mock_client` era código muerto → eliminado; refactorizado en `_base_vars()` y `_mock_fins()` reutilizables
- **Fix 6:** `run_publisher()` acepta `max_cycles: Optional[int] = None` — en producción se omite (loop infinito); en tests se pasa `max_cycles=1` o `max_cycles=2` en vez de parchear `time.sleep` con `KeyboardInterrupt`
