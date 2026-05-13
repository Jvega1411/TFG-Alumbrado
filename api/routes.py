from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from model.fase2 import Ciclo, HorarioTramo, SeccionEstado
from schemas.lectura import (
    CicloResponse,
    HorarioTramoResponse,
    SeccionEstadoResponse,
    SeccionHistorialResponse,
)

_engine = None

router = APIRouter()


def init_engine(engine) -> None:
    """Inject the SQLAlchemy engine used by request sessions."""
    global _engine
    _engine = engine


def get_db():
    if _engine is None:
        raise RuntimeError("Engine no inicializado: llamar init_engine() antes de usar el router")
    with Session(_engine) as session:
        yield session


@router.get("/api/estado", response_model=CicloResponse)
def get_estado(db: Session = Depends(get_db)):
    ciclo = db.query(Ciclo).order_by(Ciclo.id.desc()).first()
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Sin datos")
    return ciclo


@router.get("/api/secciones/actual", response_model=List[SeccionEstadoResponse])
def get_secciones_actual(db: Session = Depends(get_db)):
    ultimo_id = (
        db.query(Ciclo.id)
        .join(SeccionEstado, SeccionEstado.ciclo_id == Ciclo.id)
        .filter(Ciclo.secciones_status == "ok")
        .order_by(Ciclo.id.desc())
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
        .order_by(Ciclo.id.desc())
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
    db: Session = Depends(get_db),
):
    q = db.query(Ciclo)
    if desde is not None:
        q = q.filter(Ciclo.timestamp >= desde)
    if hasta is not None:
        q = q.filter(Ciclo.timestamp <= hasta)
    return q.order_by(Ciclo.timestamp.desc()).limit(limit).all()


@router.get("/api/historial/secciones", response_model=List[SeccionHistorialResponse])
def get_historial_secciones(
    seccion_id: Optional[int] = Query(None, ge=1, le=112),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(SeccionEstado)
    if seccion_id is not None:
        q = q.filter(SeccionEstado.seccion_id == seccion_id)
    if desde is not None:
        q = q.filter(SeccionEstado.timestamp >= desde)
    if hasta is not None:
        q = q.filter(SeccionEstado.timestamp <= hasta)
    return q.order_by(SeccionEstado.timestamp.desc()).limit(limit).all()
