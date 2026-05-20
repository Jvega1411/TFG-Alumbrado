from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config() -> AlembicConfig:
    cfg = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", "ALEMBIC_INI_URL_MUST_NOT_BE_USED")
    return cfg


def test_alembic_upgrade_uses_db_estados_url(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh.db"
    monkeypatch.setenv("DB_ESTADOS_URL", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(_config(), "head")

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    inspector = inspect(engine)
    assert {"ciclo", "seccion_estado", "horario_tramo"}.issubset(set(inspector.get_table_names()))
    assert "timestamp" in {col["name"] for col in inspector.get_columns("horario_tramo")}
    indexes = {idx["name"] for idx in inspector.get_indexes("horario_tramo")}
    assert "ix_horario_tramo_timestamp" in indexes
    assert "ix_horario_tramo_tramo_timestamp" in indexes


def test_alembic_upgrade_adds_horario_timestamp_to_existing_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "existing.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE ciclo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    fins_ok BOOLEAN NOT NULL,
                    fins_error VARCHAR(512)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE horario_tramo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ciclo_id INTEGER NOT NULL,
                    tramo_id INTEGER NOT NULL,
                    inicio_raw INTEGER,
                    fin_raw INTEGER,
                    FOREIGN KEY(ciclo_id) REFERENCES ciclo(id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO ciclo (id, timestamp, fins_ok, fins_error)
                VALUES (1, '2026-05-13 10:00:00+00:00', 1, NULL)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO horario_tramo (ciclo_id, tramo_id, inicio_raw, fin_raw)
                VALUES (1, 1, 100, 200)
                """
            )
        )

    monkeypatch.setenv("DB_ESTADOS_URL", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(_config(), "head")

    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("horario_tramo")}
    assert "timestamp" in columns
    assert columns["timestamp"]["nullable"] is False
    indexes = {idx["name"] for idx in inspector.get_indexes("horario_tramo")}
    assert "ix_horario_tramo_timestamp" in indexes
    assert "ix_horario_tramo_tramo_timestamp" in indexes

    with engine.connect() as conn:
        timestamp = conn.execute(text("SELECT timestamp FROM horario_tramo WHERE tramo_id = 1")).scalar_one()
    assert timestamp is not None
