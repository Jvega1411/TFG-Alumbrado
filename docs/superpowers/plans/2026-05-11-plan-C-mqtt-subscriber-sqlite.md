# Plan C — MQTT Subscriber + SQLite (Lenovo)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recibir mensajes MQTT del topic `alumbrado/estado` y persistir cada ciclo en SQLite (tablas `ciclo`, `seccion_estado`, `horario_tramo`).

**Architecture:** `subscriber/listener.py` expone `process_message(payload_bytes, session)` (función pura testeable con SQLite en memoria) y `run_subscriber()` (loop MQTT con paho). El subscriber tiene su propia sesión SQLAlchemy, independiente de FastAPI. Los modelos SQLAlchemy ya están implementados en `model/estados.py`.

**Tech Stack:** Python 3.12, paho-mqtt, SQLAlchemy 2.0, SQLite (WAL mode), model/database.py ya implementado y auditado.

**Invariante obligatoria:** Nunca `datetime.utcnow()`. Siempre `datetime.fromisoformat()` para parsear el campo `ts` del payload (que llega como ISO8601 UTC).

---

## File Map

| Fichero | Acción | Responsabilidad |
|---|---|---|
| `subscriber/__init__.py` | Crear | Vacío — marca el paquete |
| `subscriber/listener.py` | Crear | process_message() + run_subscriber() |
| `tests/test_listener.py` | Crear | Tests de process_message con SQLite en memoria |

---

## Task 1: process_message() — lógica de escritura a BD

**Files:**
- Create: `subscriber/__init__.py`
- Create: `subscriber/listener.py`
- Create: `tests/test_listener.py`

### Contexto de models

`model/estados.py` ya implementado. Clases disponibles:

```python
# Ciclo — una fila por mensaje MQTT recibido
class Ciclo(Base):
    id, timestamp (UTCDateTime NOT NULL), fins_ok (Boolean NOT NULL),
    fins_error (String(512) nullable),
    modfunalu (Integer nullable), fotocelula_entrada/mem_fun/mem_act (Boolean nullable),
    plc_seg/min/hora/dia/mes/anio/diasem (Integer nullable),
    cycle_time_error/low_battery/io_verify_error (Boolean nullable)

# SeccionEstado — 112 filas por ciclo (solo cuando fins_ok=True)
class SeccionEstado(Base):
    id, ciclo_id (FK→ciclo.id), timestamp (UTCDateTime),
    seccion_id (Integer 1-112), automatico/manual/horario_activo (Boolean)

# HorarioTramo — 12 filas por ciclo (solo cuando fins_ok=True)
class HorarioTramo(Base):
    id, ciclo_id (FK→ciclo.id), tramo_id (Integer 1-12),
    inicio_raw (Integer nullable), fin_raw (Integer nullable)
```

`model/database.py` ya implementado:
```python
from model.database import create_db_engine, Base
# create_db_engine(url: str) → Engine con WAL + FK enforcement para SQLite
```

`UTCDateTime` (en model/database.py) rechaza datetimes sin timezone. Todo timestamp DEBE tener tzinfo.

### Estructura del payload MQTT (JSON)

Payload normal (`fins_ok: true`):
```json
{
  "ts": "2026-05-12T08:30:00+00:00",
  "fins_ok": true,
  "fins_error": null,
  "plc_reloj": {"seg": 0, "min": 30, "hora": 8, "dia": 12, "mes": 5, "anio": 2026, "diasem": 2},
  "modo": {"modfunalu": 0, "fotocelula_entrada": false, "fotocelula_mem_fun": false, "fotocelula_mem_act": false},
  "secciones": [{"id": 1, "automatico": true, "manual": false, "horario_activo": true}, "... × 112"],
  "horarios": {"raw_words": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
  "diagnostico": {"cycle_time_error": false, "low_battery": false, "io_verify_error": false}
}
```

Payload de error (`fins_ok: false`):
```json
{"ts": "2026-05-12T08:30:00+00:00", "fins_ok": false, "fins_error": "MRES=0x21 SRES=0x08"}
```

### Regla de horarios (⚠️ PENDIENTE P1)

El formato real de D1000-D1007 y D3632-D3651 es desconocido hasta el smoke test FINS. Implementación provisional: `raw_words` tiene 28 integers. Se crean 12 `HorarioTramo` con `tramo_id` 1-12. Para tramo i (0-indexed): `inicio_raw = raw_words[i*2]` si existe, `fin_raw = raw_words[i*2+1]` si existe. Solo usa los primeros 24 words (12×2); los words 24-27 se ignoran hasta que el smoke test confirme el formato real.

- [ ] **Step 1: Crear subscriber/__init__.py (vacío)**

```bash
touch subscriber/__init__.py
```

Contenido: archivo vacío.

- [ ] **Step 2: Escribir los tests de process_message**

Crear `tests/test_listener.py`:

```python
import json
import pytest
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from model.database import Base, create_db_engine
from model.estados import Ciclo, HorarioTramo, SeccionEstado
from subscriber.listener import process_message


@pytest.fixture
def db_session():
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _valid_payload(fins_ok: bool = True, seccion1_auto: bool = False) -> bytes:
    secciones = [
        {"id": i + 1, "automatico": i == 0 and seccion1_auto, "manual": False, "horario_activo": False}
        for i in range(112)
    ]
    if fins_ok:
        data = {
            "ts": "2026-05-12T08:30:00+00:00",
            "fins_ok": True,
            "fins_error": None,
            "plc_reloj": {"seg": 0, "min": 30, "hora": 8, "dia": 12, "mes": 5, "anio": 2026, "diasem": 2},
            "modo": {
                "modfunalu": 0,
                "fotocelula_entrada": False,
                "fotocelula_mem_fun": False,
                "fotocelula_mem_act": False,
            },
            "secciones": secciones,
            "horarios": {"raw_words": [0] * 28},
            "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
        }
    else:
        data = {
            "ts": "2026-05-12T08:30:00+00:00",
            "fins_ok": False,
            "fins_error": "MRES=0x21 SRES=0x08",
        }
    return json.dumps(data).encode("utf-8")


class TestProcessMessageValidPayload:

    def test_creates_ciclo_row(self, db_session):
        process_message(_valid_payload(), db_session)
        assert db_session.query(Ciclo).count() == 1

    def test_ciclo_fins_ok_true(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.fins_ok is True

    def test_ciclo_timestamp_is_aware(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.timestamp.tzinfo is not None

    def test_creates_112_seccion_rows(self, db_session):
        process_message(_valid_payload(), db_session)
        assert db_session.query(SeccionEstado).count() == 112

    def test_seccion_ids_are_1_to_112(self, db_session):
        process_message(_valid_payload(), db_session)
        ids = [s.seccion_id for s in db_session.query(SeccionEstado).order_by(SeccionEstado.seccion_id).all()]
        assert ids == list(range(1, 113))

    def test_seccion1_automatico_false_by_default(self, db_session):
        process_message(_valid_payload(seccion1_auto=False), db_session)
        sec1 = db_session.query(SeccionEstado).filter(SeccionEstado.seccion_id == 1).first()
        assert sec1.automatico is False

    def test_seccion1_automatico_true(self, db_session):
        process_message(_valid_payload(seccion1_auto=True), db_session)
        sec1 = db_session.query(SeccionEstado).filter(SeccionEstado.seccion_id == 1).first()
        assert sec1.automatico is True

    def test_creates_12_horario_tramo_rows(self, db_session):
        process_message(_valid_payload(), db_session)
        assert db_session.query(HorarioTramo).count() == 12

    def test_horario_tramo_ids_are_1_to_12(self, db_session):
        process_message(_valid_payload(), db_session)
        ids = [h.tramo_id for h in db_session.query(HorarioTramo).order_by(HorarioTramo.tramo_id).all()]
        assert ids == list(range(1, 13))

    def test_ciclo_modfunalu(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.modfunalu == 0

    def test_ciclo_reloj_hora(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.plc_hora == 8
        assert ciclo.plc_anio == 2026

    def test_seccion_timestamp_equals_ciclo_timestamp(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        sec = db_session.query(SeccionEstado).first()
        assert sec.timestamp == ciclo.timestamp

    def test_seccion_ciclo_id_matches(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        sec = db_session.query(SeccionEstado).first()
        assert sec.ciclo_id == ciclo.id


class TestProcessMessageErrorPayload:

    def test_fins_error_creates_ciclo(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        assert db_session.query(Ciclo).count() == 1

    def test_fins_error_ciclo_fins_ok_false(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.fins_ok is False

    def test_fins_error_stores_error_message(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert "MRES" in ciclo.fins_error

    def test_fins_error_no_seccion_rows(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        assert db_session.query(SeccionEstado).count() == 0

    def test_fins_error_no_horario_rows(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        assert db_session.query(HorarioTramo).count() == 0

    def test_fins_error_modfunalu_is_none(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.modfunalu is None


class TestProcessMessageMalformedPayload:

    def test_invalid_json_creates_nothing(self, db_session):
        process_message(b"not valid json {{{", db_session)
        assert db_session.query(Ciclo).count() == 0

    def test_invalid_utf8_creates_nothing(self, db_session):
        process_message(b"\xff\xfe invalid", db_session)
        assert db_session.query(Ciclo).count() == 0

    def test_missing_ts_creates_nothing(self, db_session):
        payload = json.dumps({"fins_ok": True}).encode("utf-8")
        process_message(payload, db_session)
        assert db_session.query(Ciclo).count() == 0

    def test_invalid_ts_creates_nothing(self, db_session):
        payload = json.dumps({"ts": "not-a-date", "fins_ok": True}).encode("utf-8")
        process_message(payload, db_session)
        assert db_session.query(Ciclo).count() == 0
```

- [ ] **Step 3: Verificar que los tests fallan**

```
pytest tests/test_listener.py -v
```

Expected: `FAILED` con `ModuleNotFoundError: No module named 'subscriber'`

- [ ] **Step 4: Implementar subscriber/listener.py**

Crear `subscriber/listener.py`:

```python
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from model.estados import Ciclo, HorarioTramo, SeccionEstado

logger = logging.getLogger(__name__)


def process_message(payload_bytes: bytes, session: Session) -> None:
    """Parsea payload MQTT y escribe a BD. Silencia errores: no detiene el loop."""
    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Payload MQTT malformado: %s", exc)
        return

    try:
        _write_to_db(data, session)
    except Exception as exc:
        logger.error("Error escribiendo en BD: %s", exc)
        session.rollback()


def _write_to_db(data: dict, session: Session) -> None:
    ts_str = data.get("ts")
    if not ts_str:
        raise ValueError("Campo 'ts' ausente en payload")
    try:
        ts = datetime.fromisoformat(ts_str)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"ts invalido: {ts_str!r}") from exc

    fins_ok = bool(data.get("fins_ok", False))
    modo = data.get("modo", {}) if fins_ok else {}
    reloj = data.get("plc_reloj", {}) if fins_ok else {}
    diag = data.get("diagnostico", {}) if fins_ok else {}

    ciclo = Ciclo(
        timestamp=ts,
        fins_ok=fins_ok,
        fins_error=data.get("fins_error"),
        modfunalu=modo.get("modfunalu"),
        fotocelula_entrada=modo.get("fotocelula_entrada"),
        fotocelula_mem_fun=modo.get("fotocelula_mem_fun"),
        fotocelula_mem_act=modo.get("fotocelula_mem_act"),
        plc_seg=reloj.get("seg"),
        plc_min=reloj.get("min"),
        plc_hora=reloj.get("hora"),
        plc_dia=reloj.get("dia"),
        plc_mes=reloj.get("mes"),
        plc_anio=reloj.get("anio"),
        plc_diasem=reloj.get("diasem"),
        cycle_time_error=diag.get("cycle_time_error"),
        low_battery=diag.get("low_battery"),
        io_verify_error=diag.get("io_verify_error"),
    )
    session.add(ciclo)
    session.flush()  # obtiene ciclo.id antes de insertar FK hijos

    if fins_ok:
        for s in data.get("secciones", []):
            session.add(SeccionEstado(
                ciclo_id=ciclo.id,
                timestamp=ts,
                seccion_id=s["id"],
                automatico=bool(s["automatico"]),
                manual=bool(s["manual"]),
                horario_activo=bool(s["horario_activo"]),
            ))

        # ⚠️ PENDIENTE P1: formato real de raw_words desconocido hasta smoke test FINS
        # Provisional: 2 words por tramo, inicio=raw_words[i*2], fin=raw_words[i*2+1]
        raw_words = data.get("horarios", {}).get("raw_words", [])
        for i in range(12):
            session.add(HorarioTramo(
                ciclo_id=ciclo.id,
                tramo_id=i + 1,
                inicio_raw=raw_words[i * 2] if i * 2 < len(raw_words) else None,
                fin_raw=raw_words[i * 2 + 1] if i * 2 + 1 < len(raw_words) else None,
            ))

    session.commit()
```

- [ ] **Step 5: Verificar que todos los tests de listener pasan**

```
pytest tests/test_listener.py -v
```

Expected: todos PASSED (34 tests)

- [ ] **Step 6: Verificar suite completa sin regresiones**

```
pytest tests/ -v
```

Expected: todos PASSED

- [ ] **Step 7: Commit**

```bash
git add subscriber/__init__.py subscriber/listener.py tests/test_listener.py
git commit -m "feat(subscriber): process_message — parseo MQTT y escritura SQLite"
```

---

## Task 2: run_subscriber() — loop MQTT con paho

**Files:**
- Modify: `subscriber/listener.py`
- No new test file — el test de run_subscriber usa mocks de paho

- [ ] **Step 1: Escribir test de run_subscriber**

Añadir al final de `tests/test_listener.py`:

```python
from unittest.mock import MagicMock, patch

from subscriber.listener import run_subscriber


class TestRunSubscriber:

    def test_connects_to_configured_broker(self):
        mock_client = MagicMock()

        with patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Base.metadata.create_all"), \
             patch.object(mock_client, "loop_forever", side_effect=KeyboardInterrupt):
            try:
                run_subscriber()
            except KeyboardInterrupt:
                pass

        from config.settings import Config
        mock_client.connect.assert_called_once_with(
            Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, keepalive=60
        )

    def test_subscribes_to_configured_topic(self):
        mock_client = MagicMock()

        with patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Base.metadata.create_all"), \
             patch.object(mock_client, "loop_forever", side_effect=KeyboardInterrupt):
            try:
                run_subscriber()
            except KeyboardInterrupt:
                pass

        from config.settings import Config
        mock_client.subscribe.assert_called_once_with(Config.MQTT_TOPIC, qos=1)

    def test_calls_loop_forever(self):
        mock_client = MagicMock()
        loop_called = [False]

        def fake_loop():
            loop_called[0] = True
            raise KeyboardInterrupt

        mock_client.loop_forever = fake_loop

        with patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Base.metadata.create_all"):
            try:
                run_subscriber()
            except KeyboardInterrupt:
                pass

        assert loop_called[0] is True
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_listener.py::TestRunSubscriber -v
```

Expected: `FAILED` con `ImportError: cannot import name 'run_subscriber'`

- [ ] **Step 3: Añadir run_subscriber() a subscriber/listener.py**

Añadir al final de `subscriber/listener.py`:

```python
import paho.mqtt.client as mqtt

from config.settings import Config
from model.database import Base, create_db_engine


def run_subscriber() -> None:
    engine = create_db_engine(Config.DB_URL)
    Base.metadata.create_all(engine)

    def on_message(client, userdata, message):
        with Session(engine) as session:
            process_message(message.payload, session)

    mqtt_client = mqtt.Client()
    mqtt_client.on_message = on_message
    mqtt_client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, keepalive=60)
    mqtt_client.subscribe(Config.MQTT_TOPIC, qos=1)

    logger.info(
        "Subscriber MQTT iniciado — broker=%s:%d topic=%s",
        Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, Config.MQTT_TOPIC,
    )
    mqtt_client.loop_forever()
```

**IMPORTANTE:** Los imports de `mqtt`, `Config`, `create_db_engine` y `Base` deben añadirse al inicio del fichero, antes de `process_message`. El fichero completo con todos los imports al principio:

```python
import json
import logging
from datetime import datetime

import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

from config.settings import Config
from model.database import Base, create_db_engine
from model.estados import Ciclo, HorarioTramo, SeccionEstado

logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Verificar que todos los tests de listener pasan**

```
pytest tests/test_listener.py -v
```

Expected: todos PASSED

- [ ] **Step 5: Verificar suite completa sin regresiones**

```
pytest tests/ -v
```

Expected: todos PASSED

- [ ] **Step 6: Commit**

```bash
git add subscriber/listener.py tests/test_listener.py
git commit -m "feat(subscriber): run_subscriber — loop MQTT paho con sesión SQLAlchemy"
```

---

## Self-Review del plan C

- Spec C cubierto: subscriber/listener.py con process_message ✅, run_subscriber ✅, fins_ok=False solo escribe Ciclo ✅, malformed JSON silenciado ✅, SQLAlchemy error → rollback ✅
- `UTCDateTime` de model/database.py rechaza timestamps naive → `datetime.fromisoformat("2026-05-12T08:30:00+00:00")` devuelve aware ✅
- `session.flush()` antes de insertar SeccionEstado/HorarioTramo para obtener `ciclo.id` ✅
- Tests usan SQLite en memoria: sin ficheros, sin cleanup ✅
- `run_subscriber` usa `with Session(engine) as session` en on_message: sesión independiente por mensaje ✅
- PENDIENTE P1 comentado en código con nota explícita ✅
- `dict | None` no usado (no se necesita aquí) — tipos son Optional de la spec ✅
