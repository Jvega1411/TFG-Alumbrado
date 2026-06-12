import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


def _load_pipeline_checks():
    path = Path(__file__).parents[1] / "scripts" / "node-config" / "pipeline_checks.py"
    spec = importlib.util.spec_from_file_location("pipeline_checks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_db_url_hides_password():
    checks = _load_pipeline_checks()

    safe = checks._safe_db_url("mssql+pyodbc://user:secret@example/db")

    assert "secret" not in safe
    assert "***" in safe


def test_parser_accepts_recent_cycles_limit():
    checks = _load_pipeline_checks()

    args = checks.build_parser().parse_args(["recent-cycles", "--limit", "5"])

    assert args.limit == 5


def test_parser_accepts_schema_v3_command():
    checks = _load_pipeline_checks()

    args = checks.build_parser().parse_args(["schema-v3"])

    assert args.func is checks.schema_v3


def test_require_v3_schema_reports_missing_tables():
    checks = _load_pipeline_checks()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("create table ciclo (id integer primary key)"))
        tables = {"ciclo"}
        with pytest.raises(SystemExit, match="schema V3 incompleto"):
            checks._require_v3_schema(conn, tables)


def test_require_v3_schema_rejects_legacy_context_metadata_columns():
    checks = _load_pipeline_checks()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text(
            "create table ciclo ("
            "id integer primary key, "
            "vector_salidas_logicas_status text, "
            "vector_salidas_logicas_error text, "
            "contexto_plc_raw_status text, "
            "contexto_plc_raw_error text)"
        ))
        conn.execute(text(
            "create table seccion_estado ("
            "automatico_calculado integer, "
            "manual_activo integer, "
            "salida_interna integer)"
        ))
        conn.execute(text(
            "create table vector_salidas_logicas_state ("
            "source_range text, raw_words text, bits text)"
        ))
        conn.execute(text(
            "create table contexto_plc_raw_state ("
            "ranges text, semantic_policy text not null, warnings text not null)"
        ))
        tables = {
            "ciclo",
            "seccion_estado",
            "vector_salidas_logicas_state",
            "contexto_plc_raw_state",
        }
        with pytest.raises(SystemExit, match="raw-only incompatible"):
            checks._require_v3_schema(conn, tables)


def test_require_v3_schema_rejects_legacy_vector_mapping_columns():
    checks = _load_pipeline_checks()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text(
            "create table ciclo ("
            "id integer primary key, "
            "vector_salidas_logicas_status text, "
            "vector_salidas_logicas_error text, "
            "contexto_plc_raw_status text, "
            "contexto_plc_raw_error text)"
        ))
        conn.execute(text(
            "create table seccion_estado ("
            "automatico_calculado integer, "
            "manual_activo integer, "
            "salida_interna integer)"
        ))
        conn.execute(text(
            "create table vector_salidas_logicas_state ("
            "source_range text, raw_words text, bits text, mapping_status text)"
        ))
        conn.execute(text("create table contexto_plc_raw_state (ranges text)"))
        tables = {
            "ciclo",
            "seccion_estado",
            "vector_salidas_logicas_state",
            "contexto_plc_raw_state",
        }
        with pytest.raises(SystemExit, match="vector_salidas_logicas_state"):
            checks._require_v3_schema(conn, tables)


def test_schema_v3_accepts_missing_sqlite_when_autocreate_enabled(tmp_path, monkeypatch):
    checks = _load_pipeline_checks()
    db_path = tmp_path / "missing.db"

    class Config:
        DB_ESTADOS_URL = f"sqlite:///{db_path}"
        DB_AUTO_CREATE = True

        @classmethod
        def _validate_db(cls):
            return None

    monkeypatch.setattr(checks, "_config", lambda: Config)

    assert checks.schema_v3(None) == 0
    assert not db_path.exists()


def test_schema_v3_rejects_missing_sqlite_when_autocreate_disabled(tmp_path, monkeypatch):
    checks = _load_pipeline_checks()
    db_path = tmp_path / "missing.db"

    class Config:
        DB_ESTADOS_URL = f"sqlite:///{db_path}"
        DB_AUTO_CREATE = False

        @classmethod
        def _validate_db(cls):
            return None

    monkeypatch.setattr(checks, "_config", lambda: Config)

    with pytest.raises(SystemExit, match="DB_AUTO_CREATE=false"):
        checks.schema_v3(None)
