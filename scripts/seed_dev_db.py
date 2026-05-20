"""Seed a local dev SQLite with realistic data for UI audit/testing.
Run from project root: python scripts/seed_dev_db.py
"""
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.database import Base
from model.fase2 import Ciclo, HorarioTramo, SeccionEstado

DB_PATH = Path("data/bd_estados.db")
DB_PATH.parent.mkdir(exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}")
Base.metadata.create_all(engine)

NOW = datetime.now(timezone.utc)
random.seed(42)

# Patron realista: 80 secciones encendidas (auto+horario), 28 apagadas, 4 fallo
def section_state(i):
    if i in (7, 23, 58, 91):          # 4 fallos de lectura — fallo FINS
        return dict(automatico=False, manual=False, horario_activo=False)
    if i <= 80:                        # 80 encendidas
        return dict(automatico=True, manual=False, horario_activo=True)
    return dict(automatico=False, manual=False, horario_activo=False)  # 28 apagadas

with Session(engine) as s:
    s.query(HorarioTramo).delete()
    s.query(SeccionEstado).delete()
    s.query(Ciclo).delete()
    s.commit()

    ciclos = []
    for i in range(200):
        ts = NOW - timedelta(seconds=3 * (200 - i))
        c = Ciclo(
            timestamp=ts,
            fins_ok=True,
            fins_error=None,
            secciones_status="ok",
            modo_status="ok",
            fotocelula_status="ok",
            reloj_status="ok",
            horarios_status="ok",
            diagnostico_status="ok",
            modfunalu=1,
            fotocelula_entrada=True,
            fotocelula_mem_fun=True,
            fotocelula_mem_act=True,
            plc_seg=ts.second,
            plc_min=ts.minute,
            plc_hora=ts.hour,
            plc_dia=ts.day,
            plc_mes=ts.month,
            plc_anio=ts.year - 2000,
            plc_diasem=ts.weekday() + 1,
            cycle_time_error=False,
            low_battery=False,
            io_verify_error=False,
        )
        s.add(c)
        s.flush()
        ciclos.append(c)

        for sec_i in range(1, 113):
            st = section_state(sec_i)
            s.add(SeccionEstado(
                ciclo_id=c.id,
                timestamp=ts,
                seccion_id=sec_i,
                **st,
            ))

        for tramo in range(1, 13):
            s.add(HorarioTramo(
                ciclo_id=c.id,
                timestamp=ts,
                tramo_id=tramo,
                inicio_raw=tramo * 100,
                fin_raw=tramo * 100 + 50,
            ))

    s.commit()

print(f"Seed OK — {len(ciclos)} ciclos, 112 secciones/ciclo, 12 horarios/ciclo")
print(f"DB: {DB_PATH.resolve()}")
