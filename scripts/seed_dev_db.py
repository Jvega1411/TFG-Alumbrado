"""Seed a local dev SQLite with realistic data for UI audit/testing.
Run from project root: python scripts/seed_dev_db.py
"""
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from model.database import Base
from acquisition.decoders import decode_vector_salidas_logicas
from model.fase2 import (
    Ciclo,
    ContextoPlcRawState,
    HorarioTramo,
    SeccionEstado,
    VectorSalidasLogicasState,
)
from model.json_columns import dump_json_column

DB_PATH = Path("data/bd_estados.db")
DB_PATH.parent.mkdir(exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}")
# Dev seed data is disposable; rebuild the SQLite schema so UI checks survive
# model changes without requiring a manual database cleanup.
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

NOW = datetime.now(timezone.utc)
random.seed(42)

# Patron realista: 80 secciones con senal observada y 32 sin senal observada.
def section_state(i):
    if i <= 80:
        return dict(
            automatico_calculado=True,
            manual_activo=False,
            salida_interna=True,
        )
    return dict(
        automatico_calculado=False,
        manual_activo=False,
        salida_interna=False,
    )


VECTOR_RAW_WORDS = [0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0, 0, 0, 0, 0]
VECTOR_BITS = decode_vector_salidas_logicas(VECTOR_RAW_WORDS)
RAW_CONTEXT_RANGES = [
    {
        "area": "H",
        "source_range": "H0-H42",
        "raw_words": [0] * 43,
    },
    {"area": "H", "source_range": "H100", "raw_words": [0]},
    {"area": "W", "source_range": "W1", "raw_words": [0]},
    {
        "area": "W",
        "source_range": "W4-W13",
        "raw_words": VECTOR_RAW_WORDS,
    },
    {"area": "W", "source_range": "W25", "raw_words": [0]},
    {
        "area": "D",
        "source_range": "D100-D116",
        "raw_words": [0] * 17,
    },
    {"area": "D", "source_range": "D500-D506", "raw_words": [0] * 7},
    {"area": "D", "source_range": "D1000-D1007", "raw_words": [0] * 8},
    {
        "area": "D",
        "source_range": "D1008-D1009",
        "raw_words": [0] * 2,
    },
    {
        "area": "D",
        "source_range": "D3630-D3651",
        "raw_words": [0] * 22,
    },
    {"area": "A", "source_range": "A351-A353", "raw_words": [0] * 3},
    {"area": "A", "source_range": "A401-A402", "raw_words": [0] * 2},
]

with Session(engine) as s:
    s.query(ContextoPlcRawState).delete()
    s.query(VectorSalidasLogicasState).delete()
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
            reset_temporizado_status="ok",
            hmi_original_status="ok",
            reloj_ar_status="ok",
            vector_salidas_logicas_status="ok",
            contexto_plc_raw_status="ok",
            modfunalu=1,
            modo_label="fotocelula",
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

        s.add(VectorSalidasLogicasState(
            ciclo_id=c.id,
            source_range="W4-W13",
            raw_words=dump_json_column(VECTOR_RAW_WORDS),
            bits=dump_json_column(VECTOR_BITS),
        ))

        s.add(ContextoPlcRawState(
            ciclo_id=c.id,
            ranges=dump_json_column(RAW_CONTEXT_RANGES),
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
