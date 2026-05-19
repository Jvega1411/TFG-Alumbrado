from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from model.database import Base, create_db_engine
from model.fase2 import Ciclo, HorarioTramo, SeccionEstado


def _utc_dt(year=2026, month=5, day=12, hour=8):
    return datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def test_engine():
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def populated_engine(test_engine):
    with Session(test_engine) as session:
        ciclo = Ciclo(
            timestamp=_utc_dt(),
            fins_ok=True,
            fins_error=None,
            secciones_status="ok",
            horarios_status="ok",
            modo_status="ok",
            fotocelula_status="ok",
            reloj_status="ok",
            diagnostico_status="ok",
            modfunalu=0,
            fotocelula_entrada=False,
            fotocelula_mem_fun=False,
            fotocelula_mem_act=False,
            plc_seg=0,
            plc_min=0,
            plc_hora=8,
            plc_dia=12,
            plc_mes=5,
            plc_anio=2026,
            plc_diasem=2,
            cycle_time_error=False,
            low_battery=False,
            io_verify_error=False,
        )
        session.add(ciclo)
        session.flush()
        for i in range(112):
            session.add(
                SeccionEstado(
                    ciclo_id=ciclo.id,
                    timestamp=_utc_dt(),
                    seccion_id=i + 1,
                    automatico=i == 0,
                    manual=False,
                    horario_activo=False,
                )
            )
        for i in range(12):
            session.add(
                HorarioTramo(
                    ciclo_id=ciclo.id,
                    timestamp=_utc_dt(),
                    tramo_id=i + 1,
                    inicio_raw=None,
                    fin_raw=None,
                )
            )
        session.commit()
    return test_engine


def _make_client(engine):
    from main import app
    from api.routes import init_engine

    init_engine(engine)
    return TestClient(app)


@pytest.fixture
def api_client(populated_engine):
    return _make_client(populated_engine)


class TestGetDB:
    def test_get_db_raises_if_engine_not_initialized(self):
        from api.routes import get_db, init_engine

        init_engine(None)
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

    def test_returns_block_statuses(self, api_client):
        data = api_client.get("/api/estado").json()
        assert data["secciones_status"] == "ok"
        assert data["horarios_status"] == "ok"

    def test_returns_404_when_empty(self, test_engine):
        client = _make_client(test_engine)
        resp = client.get("/api/estado")
        assert resp.status_code == 404


class TestGetDashboardResumen:
    def test_returns_capabilities_readonly(self, api_client):
        data = api_client.get("/api/dashboard/resumen").json()

        assert data["capabilities"] == {
            "mode": "readonly",
            "can_write": False,
            "write_mode_available": False,
            "auth_required_for_write": True,
        }

    def test_counts_all_false_sections_as_apagadas(self, api_client):
        data = api_client.get("/api/dashboard/resumen").json()

        assert data["secciones"]["total"] == 112
        assert data["secciones"]["con_dato"] == 112
        assert data["secciones"]["automatico"] == 1
        assert data["secciones"]["manual"] == 0
        assert data["secciones"]["horario_activo"] == 0
        assert data["secciones"]["apagadas"] == 111

    def test_reports_block_statuses_and_reloj(self, api_client):
        data = api_client.get("/api/dashboard/resumen").json()

        assert data["bloques"]["secciones"]["status"] == "ok"
        assert data["bloques"]["diagnostico"]["status"] == "ok"
        assert data["plc_reloj"]["hora"] == 8
        assert data["frescura"]["stale_after_seconds"] == 30

    def test_returns_latest_partial_cycle_with_valid_sections(self, populated_engine):
        client = _make_client(populated_engine)
        with Session(populated_engine) as session:
            ciclo_parcial = Ciclo(
                timestamp=_utc_dt(hour=9),
                fins_ok=False,
                fins_error="diagnostico: timeout",
                secciones_status="ok",
                diagnostico_status="failed",
                diagnostico_error="timeout",
            )
            session.add(ciclo_parcial)
            session.flush()
            for i in range(112):
                session.add(
                    SeccionEstado(
                        ciclo_id=ciclo_parcial.id,
                        timestamp=_utc_dt(hour=9),
                        seccion_id=i + 1,
                        automatico=False,
                        manual=i == 0,
                        horario_activo=False,
                    )
                )
            session.commit()

        data = client.get("/api/dashboard/resumen").json()

        assert data["fins_ok"] is False
        assert data["bloques"]["diagnostico"]["status"] == "failed"
        assert data["secciones"]["manual"] == 1
        assert data["secciones"]["apagadas"] == 111

    def test_returns_404_when_empty(self, test_engine):
        client = _make_client(test_engine)
        resp = client.get("/api/dashboard/resumen")

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
        assert "timestamp" in sec1
        assert "ciclo_id" in sec1

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
        assert "timestamp" in data[0]
        assert "ciclo_id" in data[0]


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


class TestUltimoCicloValido:
    def test_estado_usa_timestamp_desc_no_id_desc(self, test_engine):
        client = _make_client(test_engine)
        with Session(test_engine) as session:
            ciclo_nuevo = Ciclo(
                timestamp=_utc_dt(hour=10),
                fins_ok=True,
                fins_error=None,
                modfunalu=10,
            )
            session.add(ciclo_nuevo)
            session.flush()
            ciclo_viejo_insertado_despues = Ciclo(
                timestamp=_utc_dt(hour=9),
                fins_ok=True,
                fins_error=None,
                modfunalu=9,
            )
            session.add(ciclo_viejo_insertado_despues)
            session.commit()

        resp = client.get("/api/estado")
        assert resp.status_code == 200
        assert resp.json()["modfunalu"] == 10

    def test_secciones_actual_usa_timestamp_desc_no_id_desc(self, test_engine):
        client = _make_client(test_engine)
        with Session(test_engine) as session:
            ciclo_nuevo = Ciclo(
                timestamp=_utc_dt(hour=10),
                fins_ok=True,
                secciones_status="ok",
            )
            session.add(ciclo_nuevo)
            session.flush()
            session.add(
                SeccionEstado(
                    ciclo_id=ciclo_nuevo.id,
                    timestamp=_utc_dt(hour=10),
                    seccion_id=1,
                    automatico=True,
                    manual=False,
                    horario_activo=False,
                )
            )

            ciclo_viejo_insertado_despues = Ciclo(
                timestamp=_utc_dt(hour=9),
                fins_ok=True,
                secciones_status="ok",
            )
            session.add(ciclo_viejo_insertado_despues)
            session.flush()
            session.add(
                SeccionEstado(
                    ciclo_id=ciclo_viejo_insertado_despues.id,
                    timestamp=_utc_dt(hour=9),
                    seccion_id=1,
                    automatico=False,
                    manual=True,
                    horario_activo=False,
                )
            )
            session.commit()

        resp = client.get("/api/secciones/actual")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["automatico"] is True
        assert data[0]["manual"] is False

    def test_horarios_usa_timestamp_desc_no_id_desc(self, test_engine):
        client = _make_client(test_engine)
        with Session(test_engine) as session:
            ciclo_nuevo = Ciclo(
                timestamp=_utc_dt(hour=10),
                fins_ok=True,
                horarios_status="ok",
            )
            session.add(ciclo_nuevo)
            session.flush()
            session.add(
                HorarioTramo(
                    ciclo_id=ciclo_nuevo.id,
                    timestamp=_utc_dt(hour=10),
                    tramo_id=1,
                    inicio_raw=100,
                    fin_raw=200,
                )
            )

            ciclo_viejo_insertado_despues = Ciclo(
                timestamp=_utc_dt(hour=9),
                fins_ok=True,
                horarios_status="ok",
            )
            session.add(ciclo_viejo_insertado_despues)
            session.flush()
            session.add(
                HorarioTramo(
                    ciclo_id=ciclo_viejo_insertado_despues.id,
                    timestamp=_utc_dt(hour=9),
                    tramo_id=1,
                    inicio_raw=900,
                    fin_raw=901,
                )
            )
            session.commit()

        resp = client.get("/api/horarios")
        assert resp.status_code == 200
        assert resp.json()[0]["inicio_raw"] == 100

    def test_secciones_actual_devuelve_ciclo_parcial_si_secciones_ok(self, populated_engine):
        from main import app
        from api.routes import init_engine

        init_engine(populated_engine)
        with Session(populated_engine) as session:
            ciclo_parcial = Ciclo(
                timestamp=_utc_dt(hour=9),
                fins_ok=False,
                fins_error="diagnostico: timeout",
                secciones_status="ok",
                diagnostico_status="failed",
                diagnostico_error="timeout",
            )
            session.add(ciclo_parcial)
            session.flush()
            for i in range(112):
                session.add(
                    SeccionEstado(
                        ciclo_id=ciclo_parcial.id,
                        timestamp=_utc_dt(hour=9),
                        seccion_id=i + 1,
                        automatico=False,
                        manual=i == 0,
                        horario_activo=False,
                    )
                )
            session.commit()

        client = TestClient(app)
        resp = client.get("/api/secciones/actual")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 112
        assert data[0]["manual"] is True

    def test_secciones_actual_404_cuando_no_hay_bloque_secciones_ok(self, test_engine):
        from main import app
        from api.routes import init_engine

        init_engine(test_engine)
        with Session(test_engine) as session:
            ciclo_error = Ciclo(
                timestamp=_utc_dt(),
                fins_ok=False,
                fins_error="timeout",
                secciones_status="failed",
                secciones_error="timeout",
            )
            session.add(ciclo_error)
            session.commit()

        client = TestClient(app)
        resp = client.get("/api/secciones/actual")
        assert resp.status_code == 404

    def test_horarios_devuelve_ciclo_parcial_si_horarios_ok(self, populated_engine):
        client = _make_client(populated_engine)
        with Session(populated_engine) as session:
            ciclo_parcial = Ciclo(
                timestamp=_utc_dt(hour=9),
                fins_ok=False,
                fins_error="secciones: timeout",
                horarios_status="ok",
                secciones_status="failed",
            )
            session.add(ciclo_parcial)
            session.flush()
            for i in range(12):
                session.add(
                    HorarioTramo(
                        ciclo_id=ciclo_parcial.id,
                        timestamp=_utc_dt(hour=9),
                        tramo_id=i + 1,
                        inicio_raw=100 + i,
                        fin_raw=200 + i,
                    )
                )
            session.commit()

        resp = client.get("/api/horarios")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["inicio_raw"] == 100


class TestReadOnlyApi:
    def test_api_routes_do_not_expose_write_methods(self):
        from main import app

        write_methods = {"POST", "PUT", "PATCH", "DELETE"}
        api_routes = [
            route
            for route in app.routes
            if getattr(route, "path", "").startswith("/api/")
        ]

        assert api_routes
        for route in api_routes:
            assert not (set(route.methods or set()) & write_methods), route.path
