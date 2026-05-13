from datetime import datetime, timezone

import pytest
import sqlalchemy.exc
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
            s.add(
                Ciclo(
                    timestamp=_ts(),
                    fins_ok=False,
                    secciones_status="ok",
                    diagnostico_status="failed",
                    diagnostico_error="timeout",
                )
            )
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
            s.add(
                SeccionEstado(
                    ciclo_id=ciclo.id,
                    timestamp=_ts(),
                    seccion_id=1,
                    automatico=True,
                    manual=False,
                    horario_activo=False,
                )
            )
            s.commit()
            assert s.query(SeccionEstado).count() == 1

    def test_fk_violation_rejected(self, engine):
        with Session(engine) as s:
            s.add(
                SeccionEstado(
                    ciclo_id=9999,
                    timestamp=_ts(),
                    seccion_id=1,
                    automatico=False,
                    manual=False,
                    horario_activo=False,
                )
            )
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
