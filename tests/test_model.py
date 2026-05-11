from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.estados import (
    BaseEstados,
    BaseHist,
    EstadoActual,
    EstadoSistema,
    HistorialSecciones,
    HistorialSistema,
)


@pytest.fixture
def engine_estados():
    engine = create_engine("sqlite:///:memory:")
    BaseEstados.metadata.create_all(engine)
    return engine


@pytest.fixture
def engine_hist():
    engine = create_engine("sqlite:///:memory:")
    BaseHist.metadata.create_all(engine)
    return engine


class TestEstadoActual:

    def test_upsert_creates_row(self, engine_estados):
        with Session(engine_estados) as s:
            s.merge(EstadoActual(
                seccion_id=1,
                automatico=True,
                manual=False,
                horario_activo=False,
                timestamp=datetime(2026, 1, 1),
                fins_ok=True,
            ))
            s.commit()
            row = s.get(EstadoActual, 1)
        assert row.automatico is True
        assert row.fins_ok is True

    def test_upsert_overwrites_existing_row(self, engine_estados):
        with Session(engine_estados) as s:
            s.merge(EstadoActual(
                seccion_id=5,
                automatico=True,
                manual=False,
                horario_activo=True,
                timestamp=datetime(2026, 1, 1),
                fins_ok=True,
            ))
            s.commit()
            s.merge(EstadoActual(
                seccion_id=5,
                automatico=False,
                manual=True,
                horario_activo=False,
                timestamp=datetime(2026, 1, 2),
                fins_ok=True,
            ))
            s.commit()
            row = s.get(EstadoActual, 5)
        assert row.automatico is False
        assert row.manual is True

    def test_accepts_112_sections(self, engine_estados):
        now = datetime.utcnow()
        with Session(engine_estados) as s:
            for i in range(1, 113):
                s.merge(EstadoActual(
                    seccion_id=i,
                    automatico=False,
                    manual=False,
                    horario_activo=False,
                    timestamp=now,
                    fins_ok=True,
                ))
            s.commit()
            count = s.query(EstadoActual).count()
        assert count == 112


class TestEstadoSistema:

    def test_upsert_always_id_1(self, engine_estados):
        with Session(engine_estados) as s:
            s.merge(EstadoSistema(
                id=1,
                modfunalu=0,
                timestamp=datetime(2026, 1, 1),
                fins_ok=True,
                error_msg=None,
            ))
            s.commit()
            s.merge(EstadoSistema(
                id=1,
                modfunalu=1,
                timestamp=datetime(2026, 1, 2),
                fins_ok=True,
                error_msg=None,
            ))
            s.commit()
            count = s.query(EstadoSistema).count()
            row = s.get(EstadoSistema, 1)
        assert count == 1
        assert row.modfunalu == 1

    def test_stores_error_msg(self, engine_estados):
        with Session(engine_estados) as s:
            s.merge(EstadoSistema(
                id=1,
                modfunalu=None,
                timestamp=datetime(2026, 1, 1),
                fins_ok=False,
                error_msg="MRES=0x21 SRES=0x08: CPU Unit status/error",
            ))
            s.commit()
            row = s.get(EstadoSistema, 1)
        assert row.fins_ok is False
        assert "MRES" in row.error_msg


class TestHistorialSecciones:

    def test_append_only_multiple_rows_same_section(self, engine_hist):
        now = datetime.utcnow()
        with Session(engine_hist) as s:
            s.add(HistorialSecciones(
                timestamp=now,
                seccion_id=1,
                automatico=True,
                manual=False,
                horario_activo=True,
            ))
            s.add(HistorialSecciones(
                timestamp=now,
                seccion_id=1,
                automatico=False,
                manual=False,
                horario_activo=False,
            ))
            s.commit()
            count = s.query(HistorialSecciones).filter_by(seccion_id=1).count()
        assert count == 2


class TestHistorialSistema:

    def test_append_stores_error(self, engine_hist):
        now = datetime.utcnow()
        with Session(engine_hist) as s:
            s.add(HistorialSistema(
                timestamp=now,
                modfunalu=None,
                fins_ok=False,
                error_msg="timeout",
            ))
            s.commit()
            row = s.query(HistorialSistema).first()
        assert row.fins_ok is False
        assert row.error_msg == "timeout"
