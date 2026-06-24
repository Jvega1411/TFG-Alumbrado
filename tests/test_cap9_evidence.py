import importlib.util
from pathlib import Path


def _load_cap9_evidence():
    path = Path(__file__).parents[1] / "scripts" / "node-config" / "cap9_evidence.py"
    spec = importlib.util.spec_from_file_location("cap9_evidence", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_safe_db_logical_redacts_password_and_user():
    helper = _load_cap9_evidence()

    result = helper.safe_db_logical(
        "mssql+pyodbc://alice:secret@example.local:1433/BD_Estados?driver=ODBC+Driver"
    )

    assert result == "mssql+pyodbc://example.local:1433/BD_Estados"
    assert "alice" not in result
    assert "secret" not in result


def test_safe_db_logical_keeps_sqlite_path(tmp_path):
    helper = _load_cap9_evidence()
    db_path = tmp_path / "bd_estados.db"

    result = helper.safe_db_logical(f"sqlite:///{db_path}")

    assert result == f"sqlite:///{db_path}"


def test_payload_counts_summarizes_v3_shape():
    helper = _load_cap9_evidence()

    data = {
        "schema_version": 3,
        "read_status": {"secciones": {"status": "ok"}, "modo": {"status": "ok"}},
        "secciones": [{}] * 112,
        "vector_salidas_logicas": {"raw_words": [0] * 10, "bits": [{}] * 160},
        "contexto_plc_raw": {"ranges": [{}] * 12},
    }

    assert helper.payload_counts(data) == {
        "schema_version": 3,
        "read_status_blocks": ["secciones", "modo"],
        "secciones": 112,
        "vector_raw_words": 10,
        "vector_bits": 160,
        "context_raw_ranges": 12,
    }


def test_api_base_url_uses_loopback_for_wildcard_bind():
    helper = _load_cap9_evidence()

    assert helper.api_base_url("0.0.0.0", 8000) == "http://127.0.0.1:8000"


def test_api_base_url_keeps_specific_host():
    helper = _load_cap9_evidence()

    assert helper.api_base_url("192.168.2.177", 8000) == "http://192.168.2.177:8000"
