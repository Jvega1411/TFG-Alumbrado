import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.routes import init_engine
from model.database import Base, create_db_engine
from model.fase2 import Ciclo
from subscriber.listener import process_message
from tests.v3_helpers import sample_payload_bytes, utc_dt


@pytest.fixture
def test_engine():
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def populated_engine(test_engine):
    with Session(test_engine) as session:
        process_message(sample_payload_bytes(), session)
    return test_engine


def _make_client(engine):
    from main import app

    init_engine(engine)
    return TestClient(app)


@pytest.fixture
def api_client(populated_engine):
    return _make_client(populated_engine)


def test_get_db_requires_engine():
    from api.routes import get_db

    init_engine(None)
    with pytest.raises(RuntimeError):
        next(get_db())


def test_estado_returns_latest_v3_cycle(api_client):
    data = api_client.get("/api/estado").json()
    assert data["fins_ok"] is True
    assert data["modo_label"] == "horarios"
    assert data["vector_salidas_logicas_status"] == "ok"
    assert data["contexto_plc_raw_status"] == "ok"


def test_dashboard_resumen_counts_operational_truth(api_client):
    data = api_client.get("/api/dashboard/resumen").json()
    assert data["secciones"]["total"] == 112
    assert data["secciones"]["con_dato"] == 112
    assert "salida_wr" not in data["secciones"]
    assert "activas" not in data["secciones"]
    assert "apagadas" not in data["secciones"]
    assert data["secciones"]["senales_observadas_activas"] == 0
    assert data["secciones"]["sin_senal_observada"] == 112
    assert data["bloques"]["hmi_original"]["status"] == "ok"
    assert data["bloques"]["contexto_plc_raw"]["status"] == "ok"
    assert data["frescura"]["stale_after_seconds"] == 3600
    assert "semantica" not in data


def test_secciones_actual_uses_v3_names(api_client):
    data = api_client.get("/api/secciones/actual").json()
    assert len(data) == 112
    sec1 = data[0]
    assert sec1["seccion_id"] == 1
    assert sec1["automatico_calculado"] is False
    assert sec1["manual_activo"] is False
    assert sec1["salida_interna"] is False
    assert sec1["senal_observada_activa"] is False
    assert sec1["estado_observable"] == "sin_senal_observada"
    assert "salida_wr" not in sec1


def test_horarios_returns_decoded_fields(api_client):
    data = api_client.get("/api/horarios").json()
    assert len(data) == 12
    assert data[0]["inicio_hora"] == 6
    assert data[0]["fin_raw_words"] == [8, 0]
    assert data[0]["source_json"]["fin_hora"] == "D1002"


def test_historial_ciclos_and_secciones(api_client):
    ciclos = api_client.get("/api/historial/ciclos").json()
    assert len(ciclos) == 1
    sections = api_client.get(f"/api/historial/secciones?ciclo_id={ciclos[0]['id']}").json()
    assert len(sections) == 112


def test_new_state_endpoints(api_client):
    ciclo_id = api_client.get("/api/estado").json()["id"]
    assert api_client.get(f"/api/ciclos/{ciclo_id}/fotocelula").status_code == 200
    reset = api_client.get(f"/api/ciclos/{ciclo_id}/reset_temporizado")
    assert reset.status_code == 200
    assert reset.json()["dm_raw_words"] == [1800, 0, 0, 0, 0, 0]
    assert api_client.get(f"/api/ciclos/{ciclo_id}/hmi_original").status_code == 200
    assert api_client.get(f"/api/ciclos/{ciclo_id}/reloj_ar").status_code == 200
    vector = api_client.get(f"/api/ciclos/{ciclo_id}/vector_salidas_logicas").json()
    assert vector["source_range"] == "W4-W13"
    assert vector["raw_words"][0] == 1
    assert len(vector["bits"]) == 160
    assert set(vector) == {"ciclo_id", "source_range", "raw_words", "bits"}
    context = api_client.get(f"/api/ciclos/{ciclo_id}/contexto_plc_raw").json()
    assert set(context) == {"ciclo_id", "ranges"}
    assert context["ranges"][0]["source_range"] == "H0-H42"
    assert set(context["ranges"][0]) == {"area", "source_range", "raw_words"}


def test_returns_404_when_empty(test_engine):
    client = _make_client(test_engine)
    assert client.get("/api/estado").status_code == 404
    assert client.get("/api/dashboard/resumen").status_code == 404
    assert client.get("/api/secciones/actual").status_code == 404


def test_dashboard_and_current_sections_use_latest_cycle_only(populated_engine):
    client = _make_client(populated_engine)
    with Session(populated_engine) as session:
        session.add(
            Ciclo(
                timestamp=utc_dt(9),
                fins_ok=False,
                fins_error="timeout secciones",
                secciones_status="failed",
                secciones_error="timeout secciones",
                horarios_status="failed",
                horarios_error="timeout horarios",
            )
        )
        session.commit()

    summary = client.get("/api/dashboard/resumen").json()
    assert summary["secciones"]["con_dato"] == 0
    assert summary["bloques"]["secciones"]["status"] == "failed"
    assert client.get("/api/secciones/actual").status_code == 404
    assert client.get("/api/horarios").status_code == 404


def test_historial_filters(test_engine):
    client = _make_client(test_engine)
    with Session(test_engine) as session:
        session.add(Ciclo(timestamp=utc_dt(8), fins_ok=True))
        session.add(Ciclo(timestamp=utc_dt(9), fins_ok=True))
        session.commit()
    assert len(client.get("/api/historial/ciclos?limit=1").json()) == 1
    assert client.get("/api/historial/ciclos?limit=1001").status_code == 422
