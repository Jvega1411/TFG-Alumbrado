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


def _v3_table_columns(checks):
    ciclo_columns = [
        "id",
        "timestamp",
        "fins_ok",
        "fins_error",
        "modfunalu",
        "modo_label",
        "fotocelula_entrada",
        "fotocelula_mem_fun",
        "fotocelula_mem_act",
        "plc_reloj_raw_words",
        "plc_reloj_encoding",
        "plc_seg",
        "plc_min",
        "plc_hora",
        "plc_dia",
        "plc_mes",
        "plc_anio",
        "plc_diasem",
        "cycle_time_error",
        "low_battery",
        "io_verify_error",
    ]
    for block in checks.READ_BLOCKS_V3:
        ciclo_columns.extend([f"{block}_status", f"{block}_error"])

    return {
        "ciclo": ciclo_columns,
        "seccion_estado": [
            "id",
            "ciclo_id",
            "timestamp",
            "seccion_id",
            "automatico_calculado",
            "manual_activo",
            "salida_interna",
        ],
        "horario_tramo": [
            "id",
            "ciclo_id",
            "timestamp",
            "tramo_id",
            "inicio_raw",
            "fin_raw",
            "inicio_raw_words",
            "fin_raw_words",
            "source_json",
            "inicio_hora",
            "inicio_minuto",
            "fin_hora",
            "fin_minuto",
        ],
        "fotocelula_state": [
            "id",
            "ciclo_id",
            "entrada_raw",
            "mem_fun",
            "filtrada_activa",
            "temporizador_activacion_s",
            "temporizador_desactivacion_s",
            "retardo_activacion_s",
            "retardo_desactivacion_s",
        ],
        "reset_temporizado_state": [
            "id",
            "ciclo_id",
            "w1_raw",
            "dm_raw_words",
            "horario_global_activo",
            "reset_activo",
            "retardo_segundo_apagado_s",
            "temporizador_segundo_apagado_s",
            "contador_apagados",
            "max_reintentos",
        ],
        "hmi_original_state": [
            "id",
            "ciclo_id",
            "indice_seccion",
            "indice_anterior",
            "h10_raw",
            "automatico_seccion_seleccionada",
            "manual_seccion_seleccionada",
            "orden_transferencia_comun",
            "indicacion_activacion_alumbrado_seccion",
        ],
        "reloj_ar_state": [
            "id",
            "ciclo_id",
            "raw_a351",
            "raw_a352",
            "raw_a353",
            "ar_minuto",
            "ar_segundo",
            "ar_dia",
            "ar_hora",
            "ar_anio",
            "ar_mes",
            "encoding",
        ],
        "vector_salidas_logicas_state": [
            "id",
            "ciclo_id",
            "source_range",
            "raw_words",
            "bits",
        ],
        "contexto_plc_raw_state": [
            "id",
            "ciclo_id",
            "ranges",
        ],
    }


def _create_complete_v3_schema(
    conn,
    checks,
    *,
    omit_table=None,
    omit_column=None,
    extra_columns=None,
):
    extra_columns = extra_columns or {}
    for table, columns in _v3_table_columns(checks).items():
        if table == omit_table:
            continue
        column_defs = []
        for column in columns:
            if omit_column == (table, column):
                continue
            column_type = "integer primary key" if column == "id" else "text"
            column_defs.append(f"{column} {column_type}")
        for column in extra_columns.get(table, []):
            column_defs.append(f"{column} text")
        conn.execute(text(f"create table {table} ({', '.join(column_defs)})"))


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


def test_require_v3_schema_accepts_complete_minimal_schema():
    checks = _load_pipeline_checks()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        _create_complete_v3_schema(conn, checks)

        checks._require_v3_schema(conn, checks._sqlite_tables(conn))


@pytest.mark.parametrize(
    "table",
    [
        "ciclo",
        "seccion_estado",
        "horario_tramo",
        "fotocelula_state",
        "reset_temporizado_state",
        "hmi_original_state",
        "reloj_ar_state",
        "vector_salidas_logicas_state",
        "contexto_plc_raw_state",
    ],
)
def test_require_v3_schema_reports_each_missing_required_table(table):
    checks = _load_pipeline_checks()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        _create_complete_v3_schema(conn, checks, omit_table=table)

        with pytest.raises(SystemExit) as exc:
            checks._require_v3_schema(conn, checks._sqlite_tables(conn))

        message = str(exc.value)
        assert "schema V3 incompleto, faltan tablas:" in message
        assert table in message


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("ciclo", "reloj_ar_status"),
        ("horario_tramo", "source_json"),
        ("fotocelula_state", "filtrada_activa"),
        ("vector_salidas_logicas_state", "raw_words"),
    ],
)
def test_require_v3_schema_reports_missing_required_column(table, column):
    checks = _load_pipeline_checks()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        _create_complete_v3_schema(conn, checks, omit_column=(table, column))

        with pytest.raises(SystemExit) as exc:
            checks._require_v3_schema(conn, checks._sqlite_tables(conn))

        message = str(exc.value)
        assert f"schema V3 incompleto en {table}, faltan columnas:" in message
        assert column in message


def test_require_v3_schema_rejects_legacy_context_metadata_columns():
    checks = _load_pipeline_checks()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        _create_complete_v3_schema(
            conn,
            checks,
            extra_columns={
                "contexto_plc_raw_state": ["semantic_policy", "warnings"],
            },
        )
        tables = checks._sqlite_tables(conn)

        with pytest.raises(SystemExit, match="raw-only incompatible"):
            checks._require_v3_schema(conn, tables)


def test_require_v3_schema_rejects_legacy_vector_mapping_columns():
    checks = _load_pipeline_checks()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        _create_complete_v3_schema(
            conn,
            checks,
            extra_columns={"vector_salidas_logicas_state": ["mapping_status"]},
        )
        tables = checks._sqlite_tables(conn)

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
