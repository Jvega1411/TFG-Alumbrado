from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from model.fase2 import Ciclo, HorarioTramo, SeccionEstado
from schemas.lectura import (
    CicloResponse,
    DashboardResumenResponse,
    HorarioTramoResponse,
    SeccionEstadoResponse,
    SeccionHistorialResponse,
)

_engine = None

router = APIRouter()

READ_BLOCKS = ("secciones", "modo", "fotocelula", "reloj", "horarios", "diagnostico")
SECTION_COUNT = 112
STALE_AFTER_SECONDS = 30


def init_engine(engine) -> None:
    """Inject the SQLAlchemy engine used by request sessions."""
    global _engine
    _engine = engine


def get_db():
    if _engine is None:
        raise RuntimeError("Engine no inicializado: llamar init_engine() antes de usar el router")
    with Session(_engine) as session:
        yield session


def _latest_ciclo(db: Session) -> Ciclo:
    ciclo = db.query(Ciclo).order_by(Ciclo.timestamp.desc(), Ciclo.id.desc()).first()
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Sin datos")
    return ciclo


def _latest_valid_secciones(db: Session) -> List[SeccionEstado]:
    ultimo_id = (
        db.query(Ciclo.id)
        .join(SeccionEstado, SeccionEstado.ciclo_id == Ciclo.id)
        .filter(Ciclo.secciones_status == "ok")
        .order_by(Ciclo.timestamp.desc(), Ciclo.id.desc())
        .limit(1)
        .scalar()
    )
    if ultimo_id is None:
        return []
    return (
        db.query(SeccionEstado)
        .filter(SeccionEstado.ciclo_id == ultimo_id)
        .order_by(SeccionEstado.seccion_id)
        .all()
    )


def _age_seconds(timestamp: Optional[datetime], now: datetime) -> Optional[int]:
    if timestamp is None:
        return None
    ts = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    return int((now - ts.astimezone(timezone.utc)).total_seconds())


def _plc_reloj(ciclo: Ciclo) -> Optional[dict]:
    values = {
        "seg": ciclo.plc_seg,
        "min": ciclo.plc_min,
        "hora": ciclo.plc_hora,
        "dia": ciclo.plc_dia,
        "mes": ciclo.plc_mes,
        "anio": ciclo.plc_anio,
        "diasem": ciclo.plc_diasem,
    }
    if all(value is None for value in values.values()):
        return None
    return values


def _section_counters(rows: List[SeccionEstado]) -> dict:
    con_dato = len(rows)
    automatico = sum(1 for row in rows if row.automatico)
    manual = sum(1 for row in rows if row.manual)
    horario_activo = sum(1 for row in rows if row.horario_activo)
    apagadas = sum(
        1
        for row in rows
        if not row.automatico and not row.manual and not row.horario_activo
    )
    return {
        "total": SECTION_COUNT,
        "con_dato": con_dato,
        "automatico": automatico,
        "manual": manual,
        "horario_activo": horario_activo,
        "apagadas": apagadas,
    }


@router.get("/api/estado", response_model=CicloResponse)
def get_estado(db: Session = Depends(get_db)):
    return _latest_ciclo(db)


@router.get("/api/dashboard/resumen", response_model=DashboardResumenResponse)
def get_dashboard_resumen(db: Session = Depends(get_db)):
    ciclo = _latest_ciclo(db)
    secciones = _latest_valid_secciones(db)
    now = datetime.now(timezone.utc)
    age = _age_seconds(ciclo.timestamp, now)
    return {
        "timestamp_rpi": ciclo.timestamp,
        "plc_reloj": _plc_reloj(ciclo),
        "fins_ok": ciclo.fins_ok,
        "fins_error": ciclo.fins_error,
        "bloques": {
            block: {
                "status": getattr(ciclo, f"{block}_status"),
                "error": getattr(ciclo, f"{block}_error"),
            }
            for block in READ_BLOCKS
        },
        "secciones": _section_counters(secciones),
        "diagnostico": {
            "cycle_time_error": ciclo.cycle_time_error,
            "low_battery": ciclo.low_battery,
            "io_verify_error": ciclo.io_verify_error,
        },
        "frescura": {
            "generated_at": now,
            "timestamp_rpi": ciclo.timestamp,
            "age_seconds": age,
            "stale_after_seconds": STALE_AFTER_SECONDS,
            "is_stale": age is None or age < 0 or age > STALE_AFTER_SECONDS,
        },
        "capabilities": {
            "mode": "readonly",
            "can_write": False,
            "write_mode_available": False,
            "auth_required_for_write": True,
        },
    }


@router.get("/api/secciones/actual", response_model=List[SeccionEstadoResponse])
def get_secciones_actual(db: Session = Depends(get_db)):
    ultimo_id = (
        db.query(Ciclo.id)
        .join(SeccionEstado, SeccionEstado.ciclo_id == Ciclo.id)
        .filter(Ciclo.secciones_status == "ok")
        .order_by(Ciclo.timestamp.desc(), Ciclo.id.desc())
        .limit(1)
        .scalar()
    )
    if ultimo_id is None:
        raise HTTPException(status_code=404, detail="Sin datos validos")
    return (
        db.query(SeccionEstado)
        .filter(SeccionEstado.ciclo_id == ultimo_id)
        .order_by(SeccionEstado.seccion_id)
        .all()
    )


@router.get("/api/horarios", response_model=List[HorarioTramoResponse])
def get_horarios(db: Session = Depends(get_db)):
    ultimo_id = (
        db.query(Ciclo.id)
        .join(HorarioTramo, HorarioTramo.ciclo_id == Ciclo.id)
        .filter(Ciclo.horarios_status == "ok")
        .order_by(Ciclo.timestamp.desc(), Ciclo.id.desc())
        .limit(1)
        .scalar()
    )
    if ultimo_id is None:
        raise HTTPException(status_code=404, detail="Sin datos validos")
    return (
        db.query(HorarioTramo)
        .filter(HorarioTramo.ciclo_id == ultimo_id)
        .order_by(HorarioTramo.tramo_id)
        .all()
    )


@router.get("/api/historial/ciclos", response_model=List[CicloResponse])
def get_historial_ciclos(
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Ciclo)
    if desde is not None:
        q = q.filter(Ciclo.timestamp >= desde)
    if hasta is not None:
        q = q.filter(Ciclo.timestamp <= hasta)
    return q.order_by(Ciclo.timestamp.desc(), Ciclo.id.desc()).offset(offset).limit(limit).all()


@router.get("/api/historial/horarios", response_model=List[HorarioTramoResponse])
def get_historial_horarios(
    ciclo_id: Optional[int] = Query(None, ge=1),
    tramo_id: Optional[int] = Query(None, ge=1, le=12),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(HorarioTramo)
    if ciclo_id is not None:
        q = q.filter(HorarioTramo.ciclo_id == ciclo_id)
    if tramo_id is not None:
        q = q.filter(HorarioTramo.tramo_id == tramo_id)
    if desde is not None:
        q = q.filter(HorarioTramo.timestamp >= desde)
    if hasta is not None:
        q = q.filter(HorarioTramo.timestamp <= hasta)
    if ciclo_id is not None:
        return q.order_by(HorarioTramo.tramo_id).limit(limit).all()
    return q.order_by(HorarioTramo.timestamp.desc(), HorarioTramo.id.desc()).limit(limit).all()


@router.get("/api/historial/secciones", response_model=List[SeccionHistorialResponse])
def get_historial_secciones(
    seccion_id: Optional[int] = Query(None, ge=1, le=112),
    ciclo_id: Optional[int] = Query(None, ge=1),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(SeccionEstado)
    if seccion_id is not None:
        q = q.filter(SeccionEstado.seccion_id == seccion_id)
    if ciclo_id is not None:
        q = q.filter(SeccionEstado.ciclo_id == ciclo_id)
    if desde is not None:
        q = q.filter(SeccionEstado.timestamp >= desde)
    if hasta is not None:
        q = q.filter(SeccionEstado.timestamp <= hasta)
    if ciclo_id is not None:
        return q.order_by(SeccionEstado.seccion_id).limit(limit).all()
    return q.order_by(SeccionEstado.timestamp.desc(), SeccionEstado.id.desc()).limit(limit).all()
