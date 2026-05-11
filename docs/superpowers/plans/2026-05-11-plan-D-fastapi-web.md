# Plan D — FastAPI + Web (Lenovo)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer los datos de SQLite via FastAPI REST (5 endpoints GET) y servir un dashboard web con 5 pestañas que visualiza el estado actual e histórico del alumbrado.

**Architecture:** `schemas/lectura.py` define los modelos Pydantic de respuesta. `api/routes.py` implementa los endpoints con `Depends(get_db)` para thread-safety. `web/` contiene HTML+CSS+JS vanilla sin frameworks. `main.py` monta todo y arranca uvicorn.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, uvicorn, vanilla HTML/CSS/JS. Sin frameworks JS. Sin Jinja2.

**Invariante obligatoria:** Nunca sesión SQLAlchemy global. Cada request HTTP usa `Depends(get_db)`. La sesión del subscriber (Plan C) es independiente de la de FastAPI.

---

## File Map

| Fichero | Acción | Responsabilidad |
|---|---|---|
| `schemas/lectura.py` | Implementar (reemplaza stub) | Modelos Pydantic de respuesta API |
| `api/routes.py` | Implementar (reemplaza stub) | Router FastAPI con 5 endpoints GET |
| `web/index.html` | Crear | Estructura HTML con 5 tabs |
| `web/static/styles.css` | Crear | CSS con variables de color (placeholder) |
| `web/static/app.js` | Crear | Fetch API + actualización DOM + auto-refresh |
| `main.py` | Implementar (reemplaza stub) | Entry point: FastAPI app + static files + uvicorn |
| `tests/test_schemas.py` | Crear | Tests de serialización Pydantic |
| `tests/test_api.py` | Crear | Tests de endpoints con TestClient + SQLite en memoria |

---

## Task 1: schemas/lectura.py — modelos Pydantic

**Files:**
- Implement: `schemas/lectura.py`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Escribir tests de schemas**

Crear `tests/test_schemas.py`:

```python
from datetime import datetime, timezone

import pytest

from schemas.lectura import (
    CicloResponse,
    HorarioTramoResponse,
    SeccionEstadoResponse,
    SeccionHistorialResponse,
)


def _utc_now():
    return datetime.now(tz=timezone.utc)


class TestCicloResponse:

    def test_from_dict(self):
        data = {
            "id": 1,
            "timestamp": _utc_now(),
            "fins_ok": True,
            "fins_error": None,
            "modfunalu": 0,
            "fotocelula_entrada": False,
            "fotocelula_mem_fun": False,
            "fotocelula_mem_act": False,
            "plc_seg": 0, "plc_min": 30, "plc_hora": 8,
            "plc_dia": 12, "plc_mes": 5, "plc_anio": 2026, "plc_diasem": 2,
            "cycle_time_error": False,
            "low_battery": False,
            "io_verify_error": False,
        }
        resp = CicloResponse(**data)
        assert resp.id == 1
        assert resp.fins_ok is True
        assert resp.modfunalu == 0

    def test_optional_fields_can_be_none(self):
        data = {
            "id": 2,
            "timestamp": _utc_now(),
            "fins_ok": False,
            "fins_error": "MRES=0x21",
            "modfunalu": None,
            "fotocelula_entrada": None,
            "fotocelula_mem_fun": None,
            "fotocelula_mem_act": None,
            "plc_seg": None, "plc_min": None, "plc_hora": None,
            "plc_dia": None, "plc_mes": None, "plc_anio": None, "plc_diasem": None,
            "cycle_time_error": None,
            "low_battery": None,
            "io_verify_error": None,
        }
        resp = CicloResponse(**data)
        assert resp.fins_ok is False
        assert resp.modfunalu is None


class TestSeccionEstadoResponse:

    def test_from_dict(self):
        data = {"seccion_id": 1, "automatico": True, "manual": False, "horario_activo": True}
        resp = SeccionEstadoResponse(**data)
        assert resp.seccion_id == 1
        assert resp.automatico is True

    def test_all_false(self):
        data = {"seccion_id": 112, "automatico": False, "manual": False, "horario_activo": False}
        resp = SeccionEstadoResponse(**data)
        assert resp.manual is False


class TestHorarioTramoResponse:

    def test_from_dict(self):
        data = {"tramo_id": 3, "inicio_raw": 480, "fin_raw": 1320}
        resp = HorarioTramoResponse(**data)
        assert resp.tramo_id == 3
        assert resp.inicio_raw == 480

    def test_nullable_fields(self):
        data = {"tramo_id": 1, "inicio_raw": None, "fin_raw": None}
        resp = HorarioTramoResponse(**data)
        assert resp.inicio_raw is None


class TestSeccionHistorialResponse:

    def test_from_dict(self):
        data = {
            "timestamp": _utc_now(),
            "seccion_id": 5,
            "automatico": True,
            "manual": False,
            "horario_activo": False,
        }
        resp = SeccionHistorialResponse(**data)
        assert resp.seccion_id == 5
        assert resp.automatico is True
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_schemas.py -v
```

Expected: `FAILED` con errores de import (schemas/lectura.py tiene solo un comentario)

- [ ] **Step 3: Implementar schemas/lectura.py**

Reemplazar el contenido de `schemas/lectura.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CicloResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    fins_ok: bool
    fins_error: Optional[str]
    modfunalu: Optional[int]
    fotocelula_entrada: Optional[bool]
    fotocelula_mem_fun: Optional[bool]
    fotocelula_mem_act: Optional[bool]
    plc_seg: Optional[int]
    plc_min: Optional[int]
    plc_hora: Optional[int]
    plc_dia: Optional[int]
    plc_mes: Optional[int]
    plc_anio: Optional[int]
    plc_diasem: Optional[int]
    cycle_time_error: Optional[bool]
    low_battery: Optional[bool]
    io_verify_error: Optional[bool]


class SeccionEstadoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seccion_id: int
    automatico: bool
    manual: bool
    horario_activo: bool


class HorarioTramoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tramo_id: int
    inicio_raw: Optional[int]
    fin_raw: Optional[int]


class SeccionHistorialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    seccion_id: int
    automatico: bool
    manual: bool
    horario_activo: bool
```

- [ ] **Step 4: Verificar que todos los tests de schemas pasan**

```
pytest tests/test_schemas.py -v
```

Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add schemas/lectura.py tests/test_schemas.py
git commit -m "feat(schemas): modelos Pydantic CicloResponse, SeccionEstadoResponse, HorarioTramoResponse, SeccionHistorialResponse"
```

---

## Task 2: api/routes.py — endpoints FastAPI

**Files:**
- Implement: `api/routes.py`
- Create: `tests/test_api.py`

### Contexto de queries

El engine se crea en `api/routes.py` a nivel de módulo usando `Config.DB_URL`. Cada request usa `Depends(get_db)`:

```python
def get_db():
    with Session(engine) as session:
        yield session
```

Queries:
- `GET /api/estado` → `db.query(Ciclo).order_by(Ciclo.id.desc()).first()`
- `GET /api/secciones/actual` → subquery de `Ciclo.id` máximo, luego filtrar `SeccionEstado.ciclo_id == ultimo_id`
- `GET /api/horarios` → `HorarioTramo` del último ciclo
- `GET /api/historial/ciclos` → `Ciclo` en rango temporal con `limit`
- `GET /api/historial/secciones` → `SeccionEstado` filtrado por `seccion_id`, rango temporal, `limit`

- [ ] **Step 1: Escribir tests de API**

Crear `tests/test_api.py`:

```python
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from model.database import Base, create_db_engine
from model.estados import Ciclo, SeccionEstado, HorarioTramo


def _utc_dt(year=2026, month=5, day=12, hour=8):
    return datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def test_engine():
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def populated_engine(test_engine):
    """Engine con un ciclo válido y 112 secciones."""
    with Session(test_engine) as session:
        ciclo = Ciclo(
            timestamp=_utc_dt(),
            fins_ok=True,
            fins_error=None,
            modfunalu=0,
            fotocelula_entrada=False,
            fotocelula_mem_fun=False,
            fotocelula_mem_act=False,
            plc_seg=0, plc_min=0, plc_hora=8,
            plc_dia=12, plc_mes=5, plc_anio=2026, plc_diasem=2,
            cycle_time_error=False,
            low_battery=False,
            io_verify_error=False,
        )
        session.add(ciclo)
        session.flush()
        for i in range(112):
            session.add(SeccionEstado(
                ciclo_id=ciclo.id,
                timestamp=_utc_dt(),
                seccion_id=i + 1,
                automatico=i == 0,  # seccion 1 en automatico
                manual=False,
                horario_activo=False,
            ))
        for i in range(12):
            session.add(HorarioTramo(
                ciclo_id=ciclo.id,
                tramo_id=i + 1,
                inicio_raw=None,
                fin_raw=None,
            ))
        session.commit()
    return test_engine


def _make_client(engine):
    """Helper: inyecta engine y devuelve TestClient. Usar init_engine, NO monkeypatch."""
    from api.routes import init_engine
    init_engine(engine)
    from main import app
    return TestClient(app)


@pytest.fixture
def api_client(populated_engine):
    """TestClient con engine inyectado vía init_engine."""
    return _make_client(populated_engine)


class TestGetDB:

    def test_get_db_raises_if_engine_not_initialized(self):
        """get_db() debe fallar explícitamente si se llama sin init_engine previo."""
        from api.routes import init_engine, get_db
        init_engine(None)  # resetear a None
        with pytest.raises(RuntimeError, match="init_engine"):
            next(get_db())


class TestGetEstado:

    def test_returns_200(self, api_client):
        resp = api_client.get("/api/estado")
        assert resp.status_code == 200

    def test_returns_fins_ok_true(self, api_client):
        data = api_client.get("/api/estado").json()
        assert data["fins_ok"] is True

    def test_returns_modfunalu(self, api_client):
        data = api_client.get("/api/estado").json()
        assert data["modfunalu"] == 0

    def test_returns_404_when_empty(self, test_engine):
        client = _make_client(test_engine)
        resp = client.get("/api/estado")
        assert resp.status_code == 404


class TestGetSeccionesActual:

    def test_returns_200(self, api_client):
        resp = api_client.get("/api/secciones/actual")
        assert resp.status_code == 200

    def test_returns_112_secciones(self, api_client):
        data = api_client.get("/api/secciones/actual").json()
        assert len(data) == 112

    def test_seccion1_automatico_true(self, api_client):
        data = api_client.get("/api/secciones/actual").json()
        sec1 = next(s for s in data if s["seccion_id"] == 1)
        assert sec1["automatico"] is True

    def test_ordered_by_seccion_id(self, api_client):
        data = api_client.get("/api/secciones/actual").json()
        ids = [s["seccion_id"] for s in data]
        assert ids == list(range(1, 113))

    def test_returns_404_when_empty(self, test_engine):
        client = _make_client(test_engine)
        resp = client.get("/api/secciones/actual")
        assert resp.status_code == 404


class TestGetHorarios:

    def test_returns_200(self, api_client):
        resp = api_client.get("/api/horarios")
        assert resp.status_code == 200

    def test_returns_12_tramos(self, api_client):
        data = api_client.get("/api/horarios").json()
        assert len(data) == 12

    def test_tramo_ids_are_1_to_12(self, api_client):
        data = api_client.get("/api/horarios").json()
        ids = [t["tramo_id"] for t in data]
        assert ids == list(range(1, 13))


class TestGetHistorialCiclos:

    def test_returns_200(self, api_client):
        resp = api_client.get("/api/historial/ciclos")
        assert resp.status_code == 200

    def test_returns_list_with_one_ciclo(self, api_client):
        data = api_client.get("/api/historial/ciclos").json()
        assert len(data) == 1

    def test_limit_param_accepted(self, api_client):
        resp = api_client.get("/api/historial/ciclos?limit=10")
        assert resp.status_code == 200

    def test_limit_above_1000_rejected(self, api_client):
        resp = api_client.get("/api/historial/ciclos?limit=1001")
        assert resp.status_code == 422


class TestGetHistorialSecciones:

    def test_returns_200(self, api_client):
        resp = api_client.get("/api/historial/secciones")
        assert resp.status_code == 200

    def test_returns_112_rows_for_one_ciclo(self, api_client):
        data = api_client.get("/api/historial/secciones").json()
        assert len(data) == 112

    def test_filter_by_seccion_id(self, api_client):
        data = api_client.get("/api/historial/secciones?seccion_id=1").json()
        assert len(data) == 1
        assert data[0]["seccion_id"] == 1

    def test_seccion_id_out_of_range_rejected(self, api_client):
        resp = api_client.get("/api/historial/secciones?seccion_id=113")
        assert resp.status_code == 422

    def test_limit_param_accepted(self, api_client):
        resp = api_client.get("/api/historial/secciones?limit=50")
        assert resp.status_code == 200
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_api.py -v
```

Expected: `FAILED` con errores de import (api/routes.py tiene solo un comentario)

- [ ] **Step 3: Implementar api/routes.py**

`api/routes.py` NO crea el engine. El engine lo inyecta `main.py` llamando a `init_engine(e)`. Esto evita que importar el módulo cree una BD y permite inyectar un engine de test sin monkeypatch frágil.

Reemplazar el contenido de `api/routes.py`:

```python
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from model.estados import Ciclo, HorarioTramo, SeccionEstado
from schemas.lectura import (
    CicloResponse,
    HorarioTramoResponse,
    SeccionEstadoResponse,
    SeccionHistorialResponse,
)

# Inicializado por main.py vía init_engine(). None hasta entonces.
_engine = None

router = APIRouter()


def init_engine(engine) -> None:
    """Inyecta el engine SQLAlchemy. Llamar desde main.py antes de registrar el router."""
    global _engine
    _engine = engine


def get_db():
    if _engine is None:
        raise RuntimeError("Engine no inicializado — llamar init_engine() antes de usar el router")
    with Session(_engine) as session:
        yield session


@router.get("/api/estado", response_model=CicloResponse)
def get_estado(db: Session = Depends(get_db)):
    ciclo = db.query(Ciclo).order_by(Ciclo.id.desc()).first()
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Sin datos")
    return ciclo


@router.get("/api/secciones/actual", response_model=List[SeccionEstadoResponse])
def get_secciones_actual(db: Session = Depends(get_db)):
    # Busca el último ciclo con fins_ok=True (que tiene filas de secciones)
    # Si el último ciclo es fins_ok=False, esto devuelve los datos del último ciclo válido
    ultimo_id = (
        db.query(Ciclo.id)
        .filter(Ciclo.fins_ok == True)  # noqa: E712
        .order_by(Ciclo.id.desc())
        .limit(1)
        .scalar()
    )
    if ultimo_id is None:
        raise HTTPException(status_code=404, detail="Sin datos válidos")
    return (
        db.query(SeccionEstado)
        .filter(SeccionEstado.ciclo_id == ultimo_id)
        .order_by(SeccionEstado.seccion_id)
        .all()
    )


@router.get("/api/horarios", response_model=List[HorarioTramoResponse])
def get_horarios(db: Session = Depends(get_db)):
    # Igual que secciones: último ciclo con fins_ok=True
    ultimo_id = (
        db.query(Ciclo.id)
        .filter(Ciclo.fins_ok == True)  # noqa: E712
        .order_by(Ciclo.id.desc())
        .limit(1)
        .scalar()
    )
    if ultimo_id is None:
        raise HTTPException(status_code=404, detail="Sin datos válidos")
    return (
        db.query(HorarioTramo)
        .filter(HorarioTramo.ciclo_id == ultimo_id)
        .order_by(HorarioTramo.tramo_id)
        .all()
    )


@router.get("/api/historial/ciclos", response_model=List[CicloResponse])
def get_historial_ciclos(
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(Ciclo)
    if desde is not None:
        q = q.filter(Ciclo.timestamp >= desde)
    if hasta is not None:
        q = q.filter(Ciclo.timestamp <= hasta)
    return q.order_by(Ciclo.timestamp.desc()).limit(limit).all()


@router.get("/api/historial/secciones", response_model=List[SeccionHistorialResponse])
def get_historial_secciones(
    seccion_id: Optional[int] = Query(None, ge=1, le=112),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(SeccionEstado)
    if seccion_id is not None:
        q = q.filter(SeccionEstado.seccion_id == seccion_id)
    if desde is not None:
        q = q.filter(SeccionEstado.timestamp >= desde)
    if hasta is not None:
        q = q.filter(SeccionEstado.timestamp <= hasta)
    return q.order_by(SeccionEstado.timestamp.desc()).limit(limit).all()
```

- [ ] **Step 4: Actualizar el fixture de tests para usar init_engine en vez de monkeypatch**

En `tests/test_api.py`, reemplazar el fixture `api_client`:

```python
@pytest.fixture
def api_client(populated_engine):
    """TestClient con engine inyectado vía init_engine."""
    import api.routes as routes_module
    routes_module.init_engine(populated_engine)

    from main import app
    return TestClient(app)
```

Y actualizar `test_returns_404_when_empty` en `TestGetEstado` y `TestGetSeccionesActual`:

```python
    def test_returns_404_when_empty(self, test_engine):
        import api.routes as routes_module
        routes_module.init_engine(test_engine)
        from main import app
        client = TestClient(app)
        resp = client.get("/api/estado")
        assert resp.status_code == 404
```

(Aplicar el mismo patrón en `TestGetSeccionesActual.test_returns_404_when_empty`.)

- [ ] **Step 5: Añadir test de "secciones devuelven último ciclo válido durante fallo FINS"**

Añadir a `tests/test_api.py`:

```python
class TestUltimoCicloValido:

    def test_secciones_actual_devuelve_ultimo_ciclo_fins_ok_durante_fallo(self, populated_engine):
        """Si el último ciclo es fins_ok=False, secciones/actual devuelve el ciclo anterior válido."""
        import api.routes as routes_module
        routes_module.init_engine(populated_engine)

        # Añadir un ciclo fins_ok=False después del ciclo válido existente
        with Session(populated_engine) as session:
            ciclo_error = Ciclo(
                timestamp=_utc_dt(hour=9),
                fins_ok=False,
                fins_error="timeout",
                modfunalu=None,
            )
            session.add(ciclo_error)
            session.commit()

        from main import app
        client = TestClient(app)
        resp = client.get("/api/secciones/actual")
        assert resp.status_code == 200
        # Debe devolver las 112 secciones del ciclo fins_ok=True anterior
        assert len(resp.json()) == 112

    def test_secciones_actual_404_cuando_nunca_hubo_ciclo_valido(self, test_engine):
        """Si no hay ningún ciclo fins_ok=True, devuelve 404."""
        import api.routes as routes_module
        routes_module.init_engine(test_engine)

        # Insertar solo un ciclo fins_ok=False
        with Session(test_engine) as session:
            ciclo_error = Ciclo(
                timestamp=_utc_dt(),
                fins_ok=False,
                fins_error="timeout",
                modfunalu=None,
            )
            session.add(ciclo_error)
            session.commit()

        from main import app
        client = TestClient(app)
        resp = client.get("/api/secciones/actual")
        assert resp.status_code == 404
```

- [ ] **Step 6: Implementar main.py**

Reemplazar el contenido de `main.py`:

```python
import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import init_engine, router
from config.settings import Config
from model.database import Base, create_db_engine

_engine = create_db_engine(Config.DB_URL)
# DB_AUTO_CREATE=true solo para desarrollo/primera vez — en producción usar `alembic upgrade head`
if Config.DB_AUTO_CREATE:
    Base.metadata.create_all(_engine)
init_engine(_engine)

app = FastAPI(title="Alumbrado Gateway")
app.include_router(router)

_web_dir = os.path.join(os.path.dirname(__file__), "web")
_static_dir = os.path.join(_web_dir, "static")

if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(_web_dir, "index.html"))


if __name__ == "__main__":
    uvicorn.run("main:app", host=Config.API_HOST, port=Config.API_PORT, reload=False)
```

- [ ] **Step 5: Verificar que todos los tests de API pasan**

```
pytest tests/test_api.py -v
```

Expected: todos PASSED

- [ ] **Step 6: Verificar suite completa sin regresiones**

```
pytest tests/ -v
```

Expected: todos PASSED

- [ ] **Step 7: Commit**

```bash
git add api/routes.py schemas/lectura.py main.py tests/test_api.py tests/test_schemas.py
git commit -m "feat(api): endpoints FastAPI GET + schemas Pydantic + entry point main.py"
```

---

## Task 3: web/index.html — dashboard con 5 pestañas

**Files:**
- Create: `web/index.html`
- Create: `web/static/styles.css`
- Create: `web/static/app.js`

No hay tests unitarios para el frontend. La verificación es manual: ejecutar el servidor y comprobar cada tab en el navegador.

- [ ] **Step 1: Crear estructura de directorios**

```bash
mkdir -p web/static
```

- [ ] **Step 2: Crear web/index.html**

Crear `web/index.html`:

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Alumbrado — TVITEC</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <header class="header">
    <h1>Alumbrado Industrial — TVITEC</h1>
    <span id="last-update" class="last-update">Cargando...</span>
    <div id="fins-error-banner" class="fins-error-banner hidden">
      <strong>⚠️ Fallo FINS:</strong> <span id="fins-error-msg"></span>
      — Datos desactualizados
    </div>
  </header>

  <nav class="tabs" role="tablist">
    <button class="tab-btn active" data-tab="sistema" role="tab">Sistema</button>
    <button class="tab-btn" data-tab="secciones" role="tab">Secciones</button>
    <button class="tab-btn" data-tab="horarios" role="tab">Horarios</button>
    <button class="tab-btn" data-tab="historico" role="tab">Histórico</button>
    <button class="tab-btn" data-tab="cerchas" role="tab">Cerchas</button>
  </nav>

  <!-- Tab 1: Sistema -->
  <section id="tab-sistema" class="tab-content active" role="tabpanel">
    <div class="cards-grid">
      <div class="card" id="card-modo">
        <h2>Modo</h2>
        <div id="modo-valor" class="card-value">—</div>
      </div>
      <div class="card" id="card-fotocelula">
        <h2>Fotocélula</h2>
        <div class="indicator-row">
          <span class="indicator-label">Entrada</span>
          <span id="ind-fot-entrada" class="indicator off"></span>
        </div>
        <div class="indicator-row">
          <span class="indicator-label">Mem. función</span>
          <span id="ind-fot-memfun" class="indicator off"></span>
        </div>
        <div class="indicator-row">
          <span class="indicator-label">Mem. activación</span>
          <span id="ind-fot-memact" class="indicator off"></span>
        </div>
      </div>
      <div class="card" id="card-reloj">
        <h2>Reloj PLC</h2>
        <div id="reloj-valor" class="card-value">—</div>
      </div>
      <div class="card" id="card-diagnostico">
        <h2>Diagnóstico</h2>
        <div class="indicator-row">
          <span class="indicator-label">Cycle time error</span>
          <span id="ind-cycle-time" class="indicator off"></span>
        </div>
        <div class="indicator-row">
          <span class="indicator-label">Low battery</span>
          <span id="ind-low-battery" class="indicator off"></span>
        </div>
        <div class="indicator-row">
          <span class="indicator-label">I/O verify error</span>
          <span id="ind-io-verify" class="indicator off"></span>
        </div>
      </div>
    </div>
  </section>

  <!-- Tab 2: Secciones -->
  <section id="tab-secciones" class="tab-content" role="tabpanel">
    <div class="legend">
      <span class="legend-item auto">Automático</span>
      <span class="legend-item manual">Manual</span>
      <span class="legend-item horario">Horario activo</span>
      <span class="legend-item off">Sin estado</span>
    </div>
    <div id="secciones-grid" class="secciones-grid"></div>
  </section>

  <!-- Tab 3: Horarios -->
  <section id="tab-horarios" class="tab-content" role="tabpanel">
    <div class="table-wrapper">
      <table class="data-table" id="horarios-table">
        <thead>
          <tr><th>Tramo</th><th>Inicio (raw)</th><th>Fin (raw)</th></tr>
        </thead>
        <tbody id="horarios-tbody"></tbody>
      </table>
    </div>
    <p class="pendiente-note">⚠️ PENDIENTE P1: formato real de horarios pendiente de smoke test FINS.</p>
  </section>

  <!-- Tab 4: Histórico -->
  <section id="tab-historico" class="tab-content" role="tabpanel">
    <form id="historico-form" class="filter-form">
      <label>Sección (1–112): <input type="number" id="hist-seccion" min="1" max="112" placeholder="Todas" /></label>
      <label>Desde: <input type="datetime-local" id="hist-desde" /></label>
      <label>Hasta: <input type="datetime-local" id="hist-hasta" /></label>
      <button type="submit" class="btn-primary">Consultar</button>
    </form>
    <div class="table-wrapper">
      <table class="data-table" id="historico-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Sección</th>
            <th>Automático</th>
            <th>Manual</th>
            <th>Horario</th>
          </tr>
        </thead>
        <tbody id="historico-tbody"></tbody>
      </table>
    </div>
    <div id="historico-load-more" class="load-more-container hidden">
      <button id="btn-load-more" class="btn-secondary">Cargar más</button>
    </div>
  </section>

  <!-- Tab 5: Cerchas -->
  <section id="tab-cerchas" class="tab-content" role="tabpanel">
    <div class="placeholder-panel">
      <p>⚠️ PENDIENTE P2: mapping sección→cercha pendiente de confirmación.</p>
    </div>
  </section>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Crear web/static/styles.css**

Crear `web/static/styles.css`:

```css
/* ⚠️ PENDIENTE P3: colores empresa pendientes — reemplazar --color-primario y --color-secundario */
:root {
  --color-primario: #10494e;
  --color-secundario: #c8dfec;
  --color-fondo: #f5f7fa;
  --color-superficie: #ffffff;
  --color-texto: #1a1a2e;
  --color-texto-suave: #6b7280;
  --color-borde: #e2e8f0;
  --color-auto: #22c55e;
  --color-manual: #f97316;
  --color-horario: #3b82f6;
  --color-off: #d1d5db;
  --color-error: #ef4444;
  --radio-borde: 8px;
  --sombra: 0 1px 3px rgba(0, 0, 0, 0.1);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--color-fondo);
  color: var(--color-texto);
  min-height: 100vh;
}

/* Header */
.header {
  background: var(--color-primario);
  color: #fff;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.header h1 { font-size: 1.25rem; font-weight: 600; }

.last-update {
  font-size: 0.8rem;
  opacity: 0.75;
  margin-left: auto;
}

.fins-error-banner {
  width: 100%;
  background: var(--color-error);
  color: #fff;
  padding: 8px 12px;
  border-radius: var(--radio-borde);
  font-size: 0.875rem;
}

.hidden { display: none !important; }

/* Tabs */
.tabs {
  background: var(--color-superficie);
  border-bottom: 2px solid var(--color-borde);
  padding: 0 24px;
  display: flex;
  gap: 4px;
}

.tab-btn {
  background: none;
  border: none;
  padding: 12px 20px;
  font-size: 0.9rem;
  cursor: pointer;
  color: var(--color-texto-suave);
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s;
}

.tab-btn:hover { color: var(--color-texto); }

.tab-btn.active {
  color: var(--color-primario);
  border-bottom-color: var(--color-primario);
  font-weight: 600;
}

/* Tab panels */
.tab-content { display: none; padding: 24px; }
.tab-content.active { display: block; }

/* Cards (Tab 1) */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.card {
  background: var(--color-superficie);
  border-radius: var(--radio-borde);
  padding: 20px;
  box-shadow: var(--sombra);
  border: 1px solid var(--color-borde);
}

.card h2 { font-size: 0.85rem; text-transform: uppercase; color: var(--color-texto-suave); margin-bottom: 12px; }

.card-value { font-size: 1.5rem; font-weight: 700; color: var(--color-primario); }

.indicator-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-borde);
  font-size: 0.875rem;
}
.indicator-row:last-child { border-bottom: none; }

.indicator {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--color-off);
}
.indicator.on { background: var(--color-auto); }
.indicator.error { background: var(--color-error); }

/* Secciones grid (Tab 2) */
.legend {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.legend-item {
  font-size: 0.8rem;
  padding: 4px 10px;
  border-radius: 9999px;
  color: #fff;
  font-weight: 500;
}
.legend-item.auto { background: var(--color-auto); }
.legend-item.manual { background: var(--color-manual); }
.legend-item.horario { background: var(--color-horario); }
.legend-item.off { background: var(--color-off); color: var(--color-texto); }

.secciones-grid {
  display: grid;
  grid-template-columns: repeat(16, 1fr);
  gap: 4px;
}

.seccion-cell {
  aspect-ratio: 1;
  border-radius: 4px;
  background: var(--color-off);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 600;
  color: #fff;
  cursor: default;
  position: relative;
}
.seccion-cell.auto { background: var(--color-auto); }
.seccion-cell.manual { background: var(--color-manual); }
.seccion-cell.horario { background: var(--color-horario); }
.seccion-cell .tooltip {
  display: none;
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0,0,0,0.8);
  color: #fff;
  font-size: 0.7rem;
  padding: 4px 8px;
  border-radius: 4px;
  white-space: nowrap;
  z-index: 10;
  pointer-events: none;
}
.seccion-cell:hover .tooltip { display: block; }

/* Tablas */
.table-wrapper { overflow-x: auto; }

.data-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-superficie);
  border-radius: var(--radio-borde);
  overflow: hidden;
  box-shadow: var(--sombra);
  font-size: 0.875rem;
}

.data-table th {
  background: var(--color-primario);
  color: #fff;
  text-align: left;
  padding: 10px 14px;
  font-weight: 500;
}

.data-table td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--color-borde);
}

.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: var(--color-fondo); }

/* Histórico */
.filter-form {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: flex-end;
  margin-bottom: 16px;
  background: var(--color-superficie);
  padding: 16px;
  border-radius: var(--radio-borde);
  box-shadow: var(--sombra);
}

.filter-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.8rem;
  color: var(--color-texto-suave);
}

.filter-form input {
  border: 1px solid var(--color-borde);
  border-radius: var(--radio-borde);
  padding: 6px 10px;
  font-size: 0.875rem;
}

.btn-primary {
  background: var(--color-primario);
  color: #fff;
  border: none;
  border-radius: var(--radio-borde);
  padding: 8px 20px;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
}
.btn-primary:hover { opacity: 0.9; }

.btn-secondary {
  background: var(--color-secundario);
  color: var(--color-primario);
  border: none;
  border-radius: var(--radio-borde);
  padding: 8px 20px;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
}

.load-more-container { margin-top: 12px; text-align: center; }

/* Placeholder */
.placeholder-panel {
  background: var(--color-superficie);
  border-radius: var(--radio-borde);
  padding: 40px;
  text-align: center;
  color: var(--color-texto-suave);
  box-shadow: var(--sombra);
}

.pendiente-note {
  margin-top: 12px;
  font-size: 0.8rem;
  color: var(--color-texto-suave);
}
```

- [ ] **Step 4: Crear web/static/app.js**

Crear `web/static/app.js`:

```javascript
'use strict';

const API = {
  estado:             '/api/estado',
  seccionesActual:    '/api/secciones/actual',
  horarios:           '/api/horarios',
  historialSecciones: '/api/historial/secciones',
};

const REFRESH_INTERVAL_MS = 15000;

let historialLimit = 200;
let historialParams = {};

// --- Tab navigation ---

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

function activeTab() {
  const active = document.querySelector('.tab-btn.active');
  return active ? active.dataset.tab : 'sistema';
}

// --- Fetch helpers ---

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

// --- FINS error banner ---

function setFinsErrorBanner(ciclo) {
  const banner = document.getElementById('fins-error-banner');
  const msg = document.getElementById('fins-error-msg');
  if (!ciclo || ciclo.fins_ok) {
    banner.classList.add('hidden');
  } else {
    banner.classList.remove('hidden');
    msg.textContent = ciclo.fins_error || 'Error desconocido';
  }
}

// --- Tab 1: Sistema ---

const MODO_LABELS = { 0: 'Horarios', 1: 'Fotocélula', 2: 'Horarios + Fotocélula' };
const MODO_COLORS = { 0: '#3b82f6', 1: '#f59e0b', 2: '#8b5cf6' };

function renderSistema(ciclo) {
  // Modo
  const modoValor = document.getElementById('modo-valor');
  if (ciclo.fins_ok && ciclo.modfunalu !== null) {
    modoValor.textContent = MODO_LABELS[ciclo.modfunalu] ?? `Código ${ciclo.modfunalu}`;
    modoValor.style.color = MODO_COLORS[ciclo.modfunalu] ?? '#1a1a2e';
  } else {
    modoValor.textContent = '—';
    modoValor.style.color = '';
  }

  // Fotocélula
  setIndicator('ind-fot-entrada',  ciclo.fins_ok && ciclo.fotocelula_entrada);
  setIndicator('ind-fot-memfun',   ciclo.fins_ok && ciclo.fotocelula_mem_fun);
  setIndicator('ind-fot-memact',   ciclo.fins_ok && ciclo.fotocelula_mem_act);

  // Reloj PLC
  const reloj = document.getElementById('reloj-valor');
  if (ciclo.fins_ok && ciclo.plc_hora !== null) {
    const pad = n => String(n).padStart(2, '0');
    reloj.textContent =
      `${pad(ciclo.plc_dia)}/${pad(ciclo.plc_mes)}/${ciclo.plc_anio} ` +
      `${pad(ciclo.plc_hora)}:${pad(ciclo.plc_min)}:${pad(ciclo.plc_seg)}`;
  } else {
    reloj.textContent = '—';
  }

  // Diagnóstico
  setIndicator('ind-cycle-time',  ciclo.fins_ok && ciclo.cycle_time_error, true);
  setIndicator('ind-low-battery', ciclo.fins_ok && ciclo.low_battery, true);
  setIndicator('ind-io-verify',   ciclo.fins_ok && ciclo.io_verify_error, true);
}

function setIndicator(id, active, isError = false) {
  const el = document.getElementById(id);
  el.classList.toggle('on', !!active && !isError);
  el.classList.toggle('error', !!active && isError);
  el.classList.toggle('off', !active);
}

// --- Tab 2: Secciones ---

function renderSecciones(secciones) {
  const grid = document.getElementById('secciones-grid');
  grid.innerHTML = '';
  secciones.forEach(s => {
    const cell = document.createElement('div');
    cell.className = 'seccion-cell';
    if (s.manual)           cell.classList.add('manual');
    else if (s.automatico)  cell.classList.add('auto');
    else if (s.horario_activo) cell.classList.add('horario');
    cell.textContent = s.seccion_id;

    const tip = document.createElement('span');
    tip.className = 'tooltip';
    tip.textContent = `S${s.seccion_id} A:${s.automatico?'✓':'✗'} M:${s.manual?'✓':'✗'} H:${s.horario_activo?'✓':'✗'}`;
    cell.appendChild(tip);
    grid.appendChild(cell);
  });
}

// --- Tab 3: Horarios ---

function renderHorarios(tramos) {
  const tbody = document.getElementById('horarios-tbody');
  tbody.innerHTML = '';
  tramos.forEach(t => {
    const tr = document.createElement('tr');
    const cells = [t.tramo_id, t.inicio_raw ?? '—', t.fin_raw ?? '—'];
    cells.forEach(val => {
      const td = document.createElement('td');
      td.textContent = val;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

// --- Tab 4: Histórico ---

document.getElementById('historico-form').addEventListener('submit', async e => {
  e.preventDefault();
  historialLimit = 200;
  historialParams = buildHistorialParams();
  await loadHistorial(true);
});

document.getElementById('btn-load-more').addEventListener('click', async () => {
  historialLimit += 200;
  await loadHistorial(false);
});

function buildHistorialParams() {
  const seccion = document.getElementById('hist-seccion').value;
  const desde   = document.getElementById('hist-desde').value;
  const hasta   = document.getElementById('hist-hasta').value;
  const params = new URLSearchParams({ limit: historialLimit });
  if (seccion) params.set('seccion_id', seccion);
  if (desde)   params.set('desde', new Date(desde).toISOString());
  if (hasta)   params.set('hasta', new Date(hasta).toISOString());
  return params;
}

async function loadHistorial(reset) {
  historialParams.set('limit', historialLimit);
  try {
    const data = await fetchJSON(`${API.historialSecciones}?${historialParams}`);
    renderHistorial(data, reset);
    document.getElementById('historico-load-more').classList.toggle('hidden', data.length < historialLimit);
  } catch (err) {
    console.error('Error cargando histórico:', err);
  }
}

function renderHistorial(rows, reset) {
  const tbody = document.getElementById('historico-tbody');
  if (reset) tbody.innerHTML = '';
  rows.forEach(r => {
    const tr = document.createElement('tr');
    const vals = [
      new Date(r.timestamp).toLocaleString('es-ES'),
      r.seccion_id,
      r.automatico ? '✓' : '—',
      r.manual ? '✓' : '—',
      r.horario_activo ? '✓' : '—',
    ];
    vals.forEach(val => {
      const td = document.createElement('td');
      td.textContent = val;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

// --- Auto-refresh ---

async function refreshAll() {
  try {
    const ciclo = await fetchJSON(API.estado);
    setFinsErrorBanner(ciclo);
    const tab = activeTab();
    if (tab === 'sistema') renderSistema(ciclo);
    if (tab === 'secciones') {
      const secciones = await fetchJSON(API.seccionesActual);
      renderSecciones(secciones);
    }
    if (tab === 'horarios') {
      const horarios = await fetchJSON(API.horarios);
      renderHorarios(horarios);
    }
    document.getElementById('last-update').textContent =
      'Actualizado: ' + new Date().toLocaleTimeString('es-ES');
  } catch (err) {
    document.getElementById('last-update').textContent = 'Error al actualizar';
    console.error('Refresh error:', err);
  }
}

refreshAll();
setInterval(refreshAll, REFRESH_INTERVAL_MS);
```

- [ ] **Step 5: Verificar el servidor y el dashboard manualmente**

Arrancar el servidor:

```bash
python main.py
```

Expected: `INFO:     Uvicorn running on http://127.0.0.1:8000` (default API_HOST=127.0.0.1; para exponer en red configurar API_HOST en .env)

Abrir `http://localhost:8000` en el navegador y verificar:

1. **Tab Sistema** — cuatro tarjetas visibles: Modo, Fotocélula, Reloj PLC, Diagnóstico
2. **Tab Secciones** — grid de 112 celdas numeradas
3. **Tab Horarios** — tabla con 12 filas (si hay datos) + nota PENDIENTE P1
4. **Tab Histórico** — formulario de filtro + tabla vacía hasta que se envíe
5. **Tab Cerchas** — mensaje de pendiente
6. Cabecera muestra "Actualizado:" con hora
7. Si la BD está vacía: sin errores en consola del navegador (el 404 del API se maneja silenciosamente)

- [ ] **Step 6: Commit**

```bash
git add web/index.html web/static/styles.css web/static/app.js
git commit -m "feat(web): dashboard HTML/CSS/JS con 5 tabs — sistema, secciones, horarios, historico, cerchas"
```

---

## Self-Review del plan D

- Spec D cubierto: 5 endpoints GET ✅, schemas Pydantic ✅, get_db() con Depends ✅, 5 tabs web ✅, refresco automático 15s ✅, banner FINS error ✅, grid 112 secciones ✅, tab Cerchas placeholder ✅
- `Optional[X]` no `X | None` en schemas — Python 3.12 OK, pero `Optional` es compatible con 3.10+ y es más explícito ✅
- `model_config = ConfigDict(from_attributes=True)` en todos los schemas para serializar desde ORM ✅
- Tests usan `monkeypatch` en `api.routes.engine` para inyectar SQLite en memoria sin tocar el engine global ✅
- `main.py` monta StaticFiles solo si el directorio existe — no falla en tests ✅
- Tab Histórico: `historialParams` se reconstruye al pulsar Consultar; `Cargar más` incrementa `limit` y recarga ✅
- PENDIENTE P3 comentado en CSS ✅
