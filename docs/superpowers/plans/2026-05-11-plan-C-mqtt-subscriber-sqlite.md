# Plan C — MQTT Subscriber + SQLite (Lenovo)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recibir mensajes MQTT del topic `alumbrado/estado` y persistir cada ciclo en SQLite (tablas `ciclo`, `seccion_estado`, `horario_tramo`).

**Architecture:** `subscriber/payload_schema.py` define un modelo Pydantic que valida cada payload recibido antes de escribir a BD (contrato estricto: 112 secciones, IDs 1..112, raw_words, tipos). `subscriber/listener.py` expone `process_message(payload_bytes, session)` (función pura testeable con SQLite en memoria) y `run_subscriber()` (loop MQTT con paho). El subscriber tiene su propia sesión SQLAlchemy, independiente de FastAPI. Los modelos Fase 2 (`Ciclo`, `SeccionEstado`, `HorarioTramo`) y `model/database.py` se crean en **Task 0** de este plan. `model/estados.py` contiene los modelos Fase 1 — **no tocar, dejar intacto**.

**Tech Stack:** Python 3.12, paho-mqtt, SQLAlchemy 2.0, Pydantic v2, SQLite (WAL mode).

**Estado real del repo al iniciar este plan:**
- `model/estados.py` existe con modelos Fase 1 (`EstadoActual`, `EstadoSistema`, `HistorialSecciones`, `HistorialSistema`) — dejar sin modificar.
- `model/database.py` NO existe — crear en Task 0.
- `model/fase2.py` NO existe — crear en Task 0 con `Ciclo`, `SeccionEstado`, `HorarioTramo`.
- `config/settings.py` tiene `DB_ESTADOS_URL`, `DB_AUTO_CREATE`, `validate_subscriber()` — usar tal cual, sin modificar.

**Invariante obligatoria:** Nunca `datetime.utcnow()`. Siempre `datetime.fromisoformat()` para parsear el campo `ts` del payload (que llega como ISO8601 UTC).

**Distinción de errores en process_message:**
- `bytes` no decodificables (UTF-8) o JSON inválido → log ERROR, no escribe, continúa
- Validación Pydantic falla (contrato de payload) → log ERROR con detalle, no escribe, continúa
- SQLAlchemy lanza excepción → log ERROR, rollback, continúa

---

## Enmienda requerida por Plan B1 - payload parcial

Plan C debe aceptar el contrato v1.1 del publisher:
- Campos top-level actuales + `schema_version` + `read_status`.
- `fins_ok=true` significa ciclo completo; `fins_ok=false` puede significar ciclo parcial, no necesariamente fallo total.
- `read_status` decide que bloques son persistibles.
- Insertar `SeccionEstado` solo si `read_status.secciones.status == "ok"`.
- Insertar `HorarioTramo` solo si `read_status.horarios.status == "ok"`.
- Persistir en `Ciclo` los campos disponibles y dejar `NULL` los campos de bloques fallidos.
- Plan D debera consultar el ultimo ciclo valido por bloque, no solo el ultimo ciclo con `fins_ok=true`.

---

## File Map

| Fichero | Acción | Responsabilidad |
|---|---|---|
| `model/database.py` | **Crear** | `Base`, `UTCDateTime`, `create_db_engine()` — Task 0 |
| `model/fase2.py` | **Crear** | `Ciclo`, `SeccionEstado`, `HorarioTramo` — Task 0 |
| `tests/test_modelo_fase2.py` | **Crear** | Smoke tests de esquema Fase 2 — Task 0 |
| `model/estados.py` | Sin cambios | Modelos Fase 1 — **no tocar** |
| `tests/test_model.py` | Sin cambios | Tests Fase 1 — **no tocar** |
| `subscriber/__init__.py` | Crear | Vacío — marca el paquete |
| `subscriber/payload_schema.py` | Crear | Validación Pydantic del payload MQTT entrante |
| `subscriber/listener.py` | Crear | process_message() + run_subscriber() |
| `tests/test_payload_schema.py` | Crear | Tests del schema de validación |
| `tests/test_listener.py` | Crear | Tests de process_message con SQLite en memoria |

---

## Task 0: Crear modelo Fase 2 — model/database.py + model/fase2.py

**Prerrequisito de todo lo demás.** Sin estos ficheros los imports de Tasks 1-3 fallan con `ModuleNotFoundError`.

**Files:**
- Crear: `model/database.py`
- Crear: `model/fase2.py`
- Crear: `tests/test_modelo_fase2.py`
- Sin cambios: `model/estados.py`, `tests/test_model.py`

- [ ] **Step 1: Crear model/database.py**

```python
from datetime import timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """DateTime que almacena UTC y rechaza valores sin timezone."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            raise ValueError(
                f"UTCDateTime requiere datetime con timezone, recibido naive: {value!r}"
            )
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


def create_db_engine(url: str):
    """Engine SQLAlchemy con WAL mode y FK enforcement para SQLite."""
    engine = create_engine(url, connect_args={"check_same_thread": False})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(conn, record):
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine
```

- [ ] **Step 2: Crear model/fase2.py**

Columnas exactas de la spec `2026-05-11-fase2-sistema-completo-design.md` sección "Subsistema C".

```python
from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, UniqueConstraint

from model.database import Base, UTCDateTime


class Ciclo(Base):
    __tablename__ = "ciclo"
    __table_args__ = (
        Index("ix_ciclo_timestamp", "timestamp"),
        UniqueConstraint("timestamp", name="uq_ciclo_timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(UTCDateTime, nullable=False)
    fins_ok = Column(Boolean, nullable=False)
    fins_error = Column(String(512), nullable=True)
    secciones_status = Column(String(16), nullable=True)
    secciones_error = Column(String(512), nullable=True)
    modo_status = Column(String(16), nullable=True)
    modo_error = Column(String(512), nullable=True)
    fotocelula_status = Column(String(16), nullable=True)
    fotocelula_error = Column(String(512), nullable=True)
    reloj_status = Column(String(16), nullable=True)
    reloj_error = Column(String(512), nullable=True)
    horarios_status = Column(String(16), nullable=True)
    horarios_error = Column(String(512), nullable=True)
    diagnostico_status = Column(String(16), nullable=True)
    diagnostico_error = Column(String(512), nullable=True)
    modfunalu = Column(Integer, nullable=True)
    fotocelula_entrada = Column(Boolean, nullable=True)
    fotocelula_mem_fun = Column(Boolean, nullable=True)
    fotocelula_mem_act = Column(Boolean, nullable=True)
    plc_seg = Column(Integer, nullable=True)
    plc_min = Column(Integer, nullable=True)
    plc_hora = Column(Integer, nullable=True)
    plc_dia = Column(Integer, nullable=True)
    plc_mes = Column(Integer, nullable=True)
    plc_anio = Column(Integer, nullable=True)
    plc_diasem = Column(Integer, nullable=True)
    cycle_time_error = Column(Boolean, nullable=True)
    low_battery = Column(Boolean, nullable=True)
    io_verify_error = Column(Boolean, nullable=True)


class SeccionEstado(Base):
    __tablename__ = "seccion_estado"
    __table_args__ = (
        Index("ix_seccion_estado_ciclo_id", "ciclo_id"),
        Index("ix_seccion_estado_timestamp", "timestamp"),
        Index("ix_seccion_estado_seccion_timestamp", "seccion_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    timestamp = Column(UTCDateTime, nullable=False)
    seccion_id = Column(Integer, nullable=False)
    automatico = Column(Boolean, nullable=False)
    manual = Column(Boolean, nullable=False)
    horario_activo = Column(Boolean, nullable=False)


class HorarioTramo(Base):
    __tablename__ = "horario_tramo"
    __table_args__ = (
        Index("ix_horario_tramo_ciclo_id", "ciclo_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo.id"), nullable=False)
    tramo_id = Column(Integer, nullable=False)
    inicio_raw = Column(Integer, nullable=True)
    fin_raw = Column(Integer, nullable=True)
```

- [ ] **Step 3: Crear tests/test_modelo_fase2.py**

```python
import pytest
import sqlalchemy.exc
from datetime import datetime, timezone

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from model.database import Base, create_db_engine
from model.fase2 import Ciclo, HorarioTramo, SeccionEstado


@pytest.fixture
def engine():
    e = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return e


def _ts(hour: int = 10) -> datetime:
    return datetime(2026, 5, 13, hour, 0, 0, tzinfo=timezone.utc)


class TestEsquema:

    def test_tablas_creadas(self, engine):
        names = inspect(engine).get_table_names()
        assert {"ciclo", "seccion_estado", "horario_tramo"}.issubset(set(names))

    def test_tablas_fase1_no_creadas(self, engine):
        names = inspect(engine).get_table_names()
        assert "estado_actual" not in names
        assert "historial_secciones" not in names


class TestCiclo:

    def test_insert_fins_ok(self, engine):
        with Session(engine) as s:
            s.add(Ciclo(timestamp=_ts(), fins_ok=True))
            s.commit()
            assert s.query(Ciclo).count() == 1

    def test_insert_fins_error(self, engine):
        with Session(engine) as s:
            s.add(Ciclo(timestamp=_ts(), fins_ok=False, fins_error="timeout"))
            s.commit()
            row = s.query(Ciclo).first()
            assert row.fins_ok is False
            assert "timeout" in row.fins_error

    def test_insert_block_statuses(self, engine):
        with Session(engine) as s:
            s.add(Ciclo(
                timestamp=_ts(),
                fins_ok=False,
                secciones_status="ok",
                diagnostico_status="failed",
                diagnostico_error="timeout",
            ))
            s.commit()
            row = s.query(Ciclo).first()
            assert row.secciones_status == "ok"
            assert row.diagnostico_status == "failed"

    def test_unique_timestamp(self, engine):
        with Session(engine) as s:
            s.add(Ciclo(timestamp=_ts(), fins_ok=True))
            s.commit()
        with Session(engine) as s:
            s.add(Ciclo(timestamp=_ts(), fins_ok=False))
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                s.commit()

    def test_naive_datetime_rejected(self, engine):
        naive = datetime(2026, 5, 13, 10, 0, 0)
        with Session(engine) as s:
            with pytest.raises((ValueError, Exception)):
                s.add(Ciclo(timestamp=naive, fins_ok=True))
                s.flush()


class TestSeccionEstado:

    def test_fk_ciclo(self, engine):
        with Session(engine) as s:
            ciclo = Ciclo(timestamp=_ts(), fins_ok=True)
            s.add(ciclo)
            s.flush()
            s.add(SeccionEstado(
                ciclo_id=ciclo.id, timestamp=_ts(),
                seccion_id=1, automatico=True, manual=False, horario_activo=False,
            ))
            s.commit()
            assert s.query(SeccionEstado).count() == 1

    def test_fk_violation_rejected(self, engine):
        with Session(engine) as s:
            s.add(SeccionEstado(
                ciclo_id=9999, timestamp=_ts(),
                seccion_id=1, automatico=False, manual=False, horario_activo=False,
            ))
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                s.commit()


class TestHorarioTramo:

    def test_fk_ciclo(self, engine):
        with Session(engine) as s:
            ciclo = Ciclo(timestamp=_ts(), fins_ok=True)
            s.add(ciclo)
            s.flush()
            s.add(HorarioTramo(ciclo_id=ciclo.id, tramo_id=1, inicio_raw=800, fin_raw=2200))
            s.commit()
            row = s.query(HorarioTramo).first()
            assert row.tramo_id == 1
            assert row.inicio_raw == 800
```

- [ ] **Step 4: Verificar que los tests pasan y los tests Fase 1 siguen intactos**

```
pytest tests/test_modelo_fase2.py -v
pytest tests/test_model.py -v
pytest tests/ -v
```

Expected: todos PASSED. Los tests de Fase 1 en `test_model.py` no deben verse afectados.

- [ ] **Step 5: Commit**

```bash
git add model/database.py model/fase2.py tests/test_modelo_fase2.py
git commit -m "feat(model): crear modelo Fase 2 — Ciclo, SeccionEstado, HorarioTramo, UTCDateTime"
```

---

## Task 1: payload_schema.py — validación Pydantic del payload MQTT

**Files:**
- Create: `subscriber/__init__.py`
- Create: `subscriber/payload_schema.py`
- Create: `tests/test_payload_schema.py`

- [ ] **Step 1: Crear subscriber/__init__.py (vacío)**

```bash
touch subscriber/__init__.py
```

Contenido: archivo vacío.

- [ ] **Step 2: Escribir tests del schema**

Crear `tests/test_payload_schema.py`:

```python
import pytest
from subscriber.payload_schema import MQTTPayload, parse_payload


def _valid_bytes(fins_ok: bool = True) -> bytes:
    import json
    secciones = [{"id": i+1, "automatico": False, "manual": False, "horario_activo": False} for i in range(112)]
    if fins_ok:
        data = {
            "ts": "2026-05-12T08:30:00+00:00",
            "fins_ok": True,
            "fins_error": None,
            "plc_reloj": {"seg": 0, "min": 30, "hora": 8, "dia": 12, "mes": 5, "anio": 2026, "diasem": 2},
            "modo": {"modfunalu": 0, "fotocelula_entrada": False, "fotocelula_mem_fun": False, "fotocelula_mem_act": False},
            "secciones": secciones,
            "horarios": {"raw_words": [0] * 28},
            "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
        }
    else:
        data = {"ts": "2026-05-12T08:30:00+00:00", "fins_ok": False, "fins_error": "timeout"}
    return json.dumps(data).encode("utf-8")


class TestParsePayload:

    def test_valid_fins_ok_payload_parses(self):
        payload = parse_payload(_valid_bytes(fins_ok=True))
        assert payload.fins_ok is True
        assert len(payload.secciones) == 112

    def test_valid_fins_error_payload_parses(self):
        payload = parse_payload(_valid_bytes(fins_ok=False))
        assert payload.fins_ok is False
        assert payload.fins_error == "timeout"
        assert payload.secciones == []

    def test_partial_payload_with_secciones_ok_parses(self):
        import json
        secciones = [{"id": i+1, "automatico": False, "manual": False, "horario_activo": False} for i in range(112)]
        data = {
            "schema_version": 1,
            "ts": "2026-05-12T08:30:00+00:00",
            "fins_ok": False,
            "fins_error": "diagnostico: timeout",
            "read_status": {
                "secciones": {"status": "ok", "error": None},
                "diagnostico": {"status": "failed", "error": "timeout"},
            },
            "secciones": secciones,
            "diagnostico": None,
        }
        payload = parse_payload(json.dumps(data).encode("utf-8"))
        assert payload.fins_ok is False
        assert payload.block_ok("secciones") is True
        assert len(payload.secciones) == 112

    def test_missing_ts_raises(self):
        import json
        data = json.dumps({"fins_ok": True}).encode("utf-8")
        with pytest.raises(ValueError, match="ts"):
            parse_payload(data)

    def test_invalid_json_raises_valueerror(self):
        with pytest.raises(ValueError, match="JSON"):
            parse_payload(b"not valid json {{{")

    def test_invalid_utf8_raises_valueerror(self):
        with pytest.raises(ValueError, match="UTF"):
            parse_payload(b"\xff\xfe invalid bytes")

    def test_wrong_seccion_count_raises(self):
        import json
        secciones = [{"id": i+1, "automatico": False, "manual": False, "horario_activo": False} for i in range(111)]
        data = {
            "ts": "2026-05-12T08:30:00+00:00", "fins_ok": True, "fins_error": None,
            "plc_reloj": {"seg": 0, "min": 0, "hora": 0, "dia": 1, "mes": 1, "anio": 2026, "diasem": 1},
            "modo": {"modfunalu": 0, "fotocelula_entrada": False, "fotocelula_mem_fun": False, "fotocelula_mem_act": False},
            "secciones": secciones,  # 111 en vez de 112
            "horarios": {"raw_words": [0] * 28},
            "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
        }
        with pytest.raises(ValueError, match="112"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_duplicate_seccion_id_raises(self):
        import json
        secciones = [{"id": 1, "automatico": False, "manual": False, "horario_activo": False}] * 112
        data = {
            "ts": "2026-05-12T08:30:00+00:00", "fins_ok": True, "fins_error": None,
            "plc_reloj": {"seg": 0, "min": 0, "hora": 0, "dia": 1, "mes": 1, "anio": 2026, "diasem": 1},
            "modo": {"modfunalu": 0, "fotocelula_entrada": False, "fotocelula_mem_fun": False, "fotocelula_mem_act": False},
            "secciones": secciones,  # todos id=1
            "horarios": {"raw_words": [0] * 28},
            "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
        }
        with pytest.raises(ValueError, match="duplicados"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_extra_field_rejected(self):
        import json
        secciones = [{"id": i+1, "automatico": False, "manual": False, "horario_activo": False} for i in range(112)]
        data = {
            "ts": "2026-05-12T08:30:00+00:00", "fins_ok": True, "fins_error": None,
            "plc_reloj": {"seg": 0, "min": 0, "hora": 0, "dia": 1, "mes": 1, "anio": 2026, "diasem": 1},
            "modo": {"modfunalu": 0, "fotocelula_entrada": False, "fotocelula_mem_fun": False, "fotocelula_mem_act": False},
            "secciones": secciones,
            "horarios": {"raw_words": [0] * 28},
            "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
            "campo_extra_inesperado": "valor",  # extra="forbid" debe rechazar esto
        }
        with pytest.raises(ValueError):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_string_coercion_rejected_for_bool(self):
        """StrictBool rechaza "true" (string) — solo acepta literal True/False de JSON."""
        import json
        secciones = [{"id": i+1, "automatico": False, "manual": False, "horario_activo": False} for i in range(112)]
        data = {
            "ts": "2026-05-12T08:30:00+00:00",
            "fins_ok": "true",  # string en vez de bool — StrictBool debe rechazar
            "fins_error": None,
            "plc_reloj": {"seg": 0, "min": 0, "hora": 0, "dia": 1, "mes": 1, "anio": 2026, "diasem": 1},
            "modo": {"modfunalu": 0, "fotocelula_entrada": False, "fotocelula_mem_fun": False, "fotocelula_mem_act": False},
            "secciones": secciones,
            "horarios": {"raw_words": [0] * 28},
            "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
        }
        with pytest.raises(ValueError):
            parse_payload(json.dumps(data).encode("utf-8"))
```

- [ ] **Step 3: Verificar que los tests fallan**

```
pytest tests/test_payload_schema.py -v
```

Expected: `FAILED` con `ModuleNotFoundError: No module named 'subscriber.payload_schema'`

- [ ] **Step 4: Implementar subscriber/payload_schema.py**

Crear `subscriber/payload_schema.py`:

```python
import json
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


class ReadBlockStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "failed", "absent"]
    error: Optional[str] = None


class SeccionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrictInt
    automatico: StrictBool
    manual: StrictBool
    horario_activo: StrictBool


class RelojPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seg: StrictInt
    min: StrictInt
    hora: StrictInt
    dia: StrictInt
    mes: StrictInt
    anio: StrictInt
    diasem: StrictInt


class ModoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modfunalu: StrictInt
    fotocelula_entrada: StrictBool
    fotocelula_mem_fun: StrictBool
    fotocelula_mem_act: StrictBool


class HorariosPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # ⚠️ PENDIENTE P1: longitud esperada (28) y rango semántico se confirmarán con smoke test
    raw_words: List[StrictInt] = Field(default_factory=list)


class DiagnosticoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_time_error: StrictBool
    low_battery: StrictBool
    io_verify_error: StrictBool


class MQTTPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Optional[StrictInt] = None
    ts: datetime
    fins_ok: StrictBool
    fins_error: Optional[str] = None
    read_status: Optional[Dict[str, ReadBlockStatus]] = None
    plc_reloj: Optional[RelojPayload] = None
    modo: Optional[ModoPayload] = None
    secciones: List[SeccionPayload] = Field(default_factory=list)
    horarios: Optional[HorariosPayload] = None
    diagnostico: Optional[DiagnosticoPayload] = None

    @model_validator(mode="after")
    def validate_secciones_when_block_ok(self) -> "MQTTPayload":
        if self.block_ok("secciones"):
            if len(self.secciones) != 112:
                raise ValueError(
                    f"bloque secciones ok requiere exactamente 112 secciones, recibidas: {len(self.secciones)}"
                )
            ids = [s.id for s in self.secciones]
            if len(set(ids)) != 112:
                raise ValueError("IDs de secciones duplicados en el payload")
            if sorted(ids) != list(range(1, 113)):
                raise ValueError("IDs de secciones deben ser 1..112")
        return self

    def block_status(self, block: str) -> Optional[str]:
        if self.read_status is not None:
            rs = self.read_status.get(block)
            return rs.status if rs is not None else None
        return "ok" if self.fins_ok else "failed"

    def block_error(self, block: str) -> Optional[str]:
        if self.read_status is not None:
            rs = self.read_status.get(block)
            return rs.error if rs is not None else None
        return None if self.fins_ok else self.fins_error

    def block_ok(self, block: str) -> bool:
        """True si el bloque fue leído correctamente.

        Con read_status (B1): comprueba status == 'ok'.
        Sin read_status (payloads legacy): fallback a fins_ok global.
        """
        if self.read_status is not None:
            rs = self.read_status.get(block)
            return rs is not None and rs.status == "ok"
        return self.fins_ok


def parse_payload(payload_bytes: bytes) -> MQTTPayload:
    """Decodifica y valida un payload MQTT. Lanza ValueError si algo falla."""
    try:
        text = payload_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"UTF-8 decode error: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc}") from exc
    return MQTTPayload.model_validate(data)
```

- [ ] **Step 5: Verificar que los tests pasan**

```
pytest tests/test_payload_schema.py -v
```

Expected: todos PASSED

- [ ] **Step 6: Commit**

```bash
git add subscriber/__init__.py subscriber/payload_schema.py tests/test_payload_schema.py
git commit -m "feat(subscriber): payload_schema — validación Pydantic estricta del payload MQTT"
```

---

## Task 2: process_message() — lógica de escritura a BD

**Files:**
- Create: `subscriber/listener.py`
- Create: `tests/test_listener.py`

### Contexto de models

Creados en Task 0. Imports correctos:

```python
from model.database import Base, create_db_engine   # model/database.py — Task 0
from model.fase2 import Ciclo, HorarioTramo, SeccionEstado  # model/fase2.py — Task 0
```

Clases disponibles tras Task 0:

```python
# model/fase2.py — Ciclo: una fila por mensaje MQTT recibido
class Ciclo(Base):
    id, timestamp (UTCDateTime NOT NULL), fins_ok (Boolean NOT NULL),
    fins_error (String(512) nullable),
    secciones_status/secciones_error, modo_status/modo_error,
    fotocelula_status/fotocelula_error, reloj_status/reloj_error,
    horarios_status/horarios_error, diagnostico_status/diagnostico_error,
    modfunalu (Integer nullable), fotocelula_entrada/mem_fun/mem_act (Boolean nullable),
    plc_seg/min/hora/dia/mes/anio/diasem (Integer nullable),
    cycle_time_error/low_battery/io_verify_error (Boolean nullable)

# model/fase2.py — SeccionEstado: 112 filas por ciclo (solo cuando read_status.secciones.status == "ok")
class SeccionEstado(Base):
    id, ciclo_id (FK→ciclo.id), timestamp (UTCDateTime),
    seccion_id (Integer 1-112), automatico/manual/horario_activo (Boolean)

# model/fase2.py — HorarioTramo: 12 filas por ciclo (solo cuando read_status.horarios.status == "ok")
class HorarioTramo(Base):
    id, ciclo_id (FK→ciclo.id), tramo_id (Integer 1-12),
    inicio_raw (Integer nullable), fin_raw (Integer nullable)
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
from model.fase2 import Ciclo, HorarioTramo, SeccionEstado
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


def _partial_payload(secciones_ok: bool = True, horarios_ok: bool = True) -> bytes:
    secciones = [
        {"id": i + 1, "automatico": i == 0, "manual": False, "horario_activo": False}
        for i in range(112)
    ]
    data = {
        "schema_version": 1,
        "ts": "2026-05-12T08:30:00+00:00",
        "fins_ok": False,
        "fins_error": "diagnostico: timeout",
        "read_status": {
            "secciones": {"status": "ok" if secciones_ok else "failed", "error": None if secciones_ok else "timeout"},
            "modo": {"status": "ok", "error": None},
            "fotocelula": {"status": "ok", "error": None},
            "reloj": {"status": "ok", "error": None},
            "horarios": {"status": "ok" if horarios_ok else "failed", "error": None if horarios_ok else "timeout"},
            "diagnostico": {"status": "failed", "error": "timeout"},
        },
        "plc_reloj": {"seg": 0, "min": 30, "hora": 8, "dia": 12, "mes": 5, "anio": 2026, "diasem": 2},
        "modo": {"modfunalu": 0, "fotocelula_entrada": False, "fotocelula_mem_fun": False, "fotocelula_mem_act": False},
        "secciones": secciones if secciones_ok else [],
        "horarios": {"raw_words": [0] * 28} if horarios_ok else None,
        "diagnostico": None,
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


class TestProcessMessagePartialPayload:

    def test_partial_with_secciones_ok_creates_seccion_rows(self, db_session):
        process_message(_partial_payload(secciones_ok=True, horarios_ok=False), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.fins_ok is False
        assert ciclo.secciones_status == "ok"
        assert ciclo.diagnostico_status == "failed"
        assert db_session.query(SeccionEstado).count() == 112

    def test_partial_with_horarios_ok_creates_horario_rows(self, db_session):
        process_message(_partial_payload(secciones_ok=False, horarios_ok=True), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.horarios_status == "ok"
        assert db_session.query(HorarioTramo).count() == 12

    def test_partial_with_secciones_failed_creates_no_seccion_rows(self, db_session):
        process_message(_partial_payload(secciones_ok=False, horarios_ok=True), db_session)
        assert db_session.query(SeccionEstado).count() == 0


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

- [ ] **Step 3: Añadir test de payload incompleto (fins_ok=True con 111 secciones)**

Añadir a `TestProcessMessageMalformedPayload` en `tests/test_listener.py`:

```python
    def test_incomplete_secciones_creates_nothing(self, db_session):
        import json
        secciones = [{"id": i+1, "automatico": False, "manual": False, "horario_activo": False} for i in range(111)]
        data = {
            "ts": "2026-05-12T08:30:00+00:00", "fins_ok": True, "fins_error": None,
            "plc_reloj": {"seg": 0, "min": 0, "hora": 0, "dia": 1, "mes": 1, "anio": 2026, "diasem": 1},
            "modo": {"modfunalu": 0, "fotocelula_entrada": False, "fotocelula_mem_fun": False, "fotocelula_mem_act": False},
            "secciones": secciones,  # 111 en vez de 112 — violación de contrato
            "horarios": {"raw_words": [0] * 28},
            "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
        }
        process_message(json.dumps(data).encode("utf-8"), db_session)
        assert db_session.query(Ciclo).count() == 0
```

- [ ] **Step 4: Verificar que los tests fallan**

```
pytest tests/test_listener.py -v
```

Expected: `FAILED` con `ModuleNotFoundError: No module named 'subscriber.listener'`

- [ ] **Step 5: Implementar subscriber/listener.py**

Crear `subscriber/listener.py`. Usa `parse_payload` de `subscriber/payload_schema.py` para validar antes de escribir. Distingue tres tipos de error:
- `ValueError` (decode/JSON/validación contrato) → log ERROR sin rollback (BD intacta)
- `SQLAlchemyError` → log ERROR + rollback
- Resto de excepciones → log ERROR + rollback (defensa)

```python
import logging

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from model.fase2 import Ciclo, HorarioTramo, SeccionEstado
from subscriber.payload_schema import parse_payload

logger = logging.getLogger(__name__)


def process_message(payload_bytes: bytes, session: Session) -> None:
    """Parsea payload MQTT y escribe a BD. Distingue errores; no detiene el loop."""
    try:
        payload = parse_payload(payload_bytes)
    except (ValueError, ValidationError) as exc:
        logger.error("Payload MQTT inválido (descartado): %s", exc)
        return

    try:
        _write_to_db(payload, session)
    except SQLAlchemyError as exc:
        logger.error("Error SQLAlchemy (rollback): %s", exc)
        session.rollback()
    except Exception as exc:
        logger.error("Error inesperado en BD (rollback): %s", exc)
        session.rollback()


def _write_to_db(payload, session: Session) -> None:
    ts = payload.ts

    ciclo = Ciclo(
        timestamp=ts,
        fins_ok=payload.fins_ok,
        fins_error=payload.fins_error,
        secciones_status=payload.block_status("secciones"),
        secciones_error=payload.block_error("secciones"),
        modo_status=payload.block_status("modo"),
        modo_error=payload.block_error("modo"),
        fotocelula_status=payload.block_status("fotocelula"),
        fotocelula_error=payload.block_error("fotocelula"),
        reloj_status=payload.block_status("reloj"),
        reloj_error=payload.block_error("reloj"),
        horarios_status=payload.block_status("horarios"),
        horarios_error=payload.block_error("horarios"),
        diagnostico_status=payload.block_status("diagnostico"),
        diagnostico_error=payload.block_error("diagnostico"),
        modfunalu=payload.modo.modfunalu if payload.modo else None,
        fotocelula_entrada=payload.modo.fotocelula_entrada if payload.modo else None,
        fotocelula_mem_fun=payload.modo.fotocelula_mem_fun if payload.modo else None,
        fotocelula_mem_act=payload.modo.fotocelula_mem_act if payload.modo else None,
        plc_seg=payload.plc_reloj.seg if payload.plc_reloj else None,
        plc_min=payload.plc_reloj.min if payload.plc_reloj else None,
        plc_hora=payload.plc_reloj.hora if payload.plc_reloj else None,
        plc_dia=payload.plc_reloj.dia if payload.plc_reloj else None,
        plc_mes=payload.plc_reloj.mes if payload.plc_reloj else None,
        plc_anio=payload.plc_reloj.anio if payload.plc_reloj else None,
        plc_diasem=payload.plc_reloj.diasem if payload.plc_reloj else None,
        cycle_time_error=payload.diagnostico.cycle_time_error if payload.diagnostico else None,
        low_battery=payload.diagnostico.low_battery if payload.diagnostico else None,
        io_verify_error=payload.diagnostico.io_verify_error if payload.diagnostico else None,
    )
    session.add(ciclo)
    session.flush()  # obtiene ciclo.id antes de insertar FK hijos

    # Insertar secciones solo si el bloque secciones fue leído correctamente
    # (fins_ok puede ser False por otros bloques fallidos — ciclo parcial Plan B1)
    if payload.block_ok("secciones") and payload.secciones:
        for s in payload.secciones:
            session.add(SeccionEstado(
                ciclo_id=ciclo.id,
                timestamp=ts,
                seccion_id=s.id,
                automatico=s.automatico,
                manual=s.manual,
                horario_activo=s.horario_activo,
            ))

    # Insertar horarios solo si el bloque horarios fue leído correctamente
    # ⚠️ PENDIENTE P1: formato real de raw_words desconocido hasta smoke test FINS
    # Provisional: 2 words por tramo, inicio=raw_words[i*2], fin=raw_words[i*2+1]
    if payload.block_ok("horarios") and payload.horarios:
        raw_words = payload.horarios.raw_words
        for i in range(12):
            session.add(HorarioTramo(
                ciclo_id=ciclo.id,
                tramo_id=i + 1,
                inicio_raw=raw_words[i * 2] if i * 2 < len(raw_words) else None,
                fin_raw=raw_words[i * 2 + 1] if i * 2 + 1 < len(raw_words) else None,
            ))

    session.commit()
```

- [ ] **Step 6: Verificar que todos los tests de listener pasan**

```
pytest tests/test_listener.py -v
```

Expected: todos PASSED

- [ ] **Step 7: Verificar suite completa sin regresiones**

```
pytest tests/ -v
```

Expected: todos PASSED

- [ ] **Step 8: Commit**

```bash
git add subscriber/listener.py tests/test_listener.py
git commit -m "feat(subscriber): process_message — validación payload + distinción errores BD"
```

---

## Task 3: run_subscriber() — loop MQTT con paho

**Files:**
- Modify: `subscriber/listener.py`
- No new test file — el test de run_subscriber usa mocks de paho

- [ ] **Step 1: Escribir test de run_subscriber**

Añadir al final de `tests/test_listener.py`:

```python
from unittest.mock import MagicMock, patch

from subscriber.listener import run_subscriber


class TestRunSubscriber:
    """
    Todos los tests parchean Config.validate_subscriber para evitar que falle
    por MQTT_BROKER_HOST vacío (default en tests). El comportamiento de validate_subscriber
    está cubierto por tests/test_settings.py.
    """

    def test_connects_to_configured_broker(self):
        mock_client = MagicMock()

        with patch("subscriber.listener.Config.validate_subscriber"), \
             patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Config.DB_AUTO_CREATE", False), \
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

        with patch("subscriber.listener.Config.validate_subscriber"), \
             patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Config.DB_AUTO_CREATE", False), \
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

        with patch("subscriber.listener.Config.validate_subscriber"), \
             patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Config.DB_AUTO_CREATE", False):
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
    Config.validate_subscriber()

    engine = create_db_engine(Config.DB_ESTADOS_URL)
    # DB_AUTO_CREATE=true solo para desarrollo/primera vez — en producción usar alembic upgrade head
    if Config.DB_AUTO_CREATE:
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
from model.fase2 import Ciclo, HorarioTramo, SeccionEstado

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

- Spec C cubierto: subscriber/listener.py con process_message ✅, run_subscriber ✅, `fins_ok=false` admite ciclos parciales y los hijos se insertan por `read_status` ✅, malformed JSON silenciado ✅, SQLAlchemy error → rollback ✅
- `UTCDateTime` de model/database.py rechaza timestamps naive → `datetime.fromisoformat("2026-05-12T08:30:00+00:00")` devuelve aware ✅
- `session.flush()` antes de insertar SeccionEstado/HorarioTramo para obtener `ciclo.id` ✅
- Tests usan SQLite en memoria: sin ficheros, sin cleanup ✅
- `run_subscriber` usa `with Session(engine) as session` en on_message: sesión independiente por mensaje ✅
- PENDIENTE P1 comentado en código con nota explícita ✅
- `dict | None` no usado (no se necesita aquí) — tipos son Optional de la spec ✅
