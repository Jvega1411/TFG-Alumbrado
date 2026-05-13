from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CicloResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    fins_ok: bool
    fins_error: Optional[str]
    secciones_status: Optional[str] = None
    secciones_error: Optional[str] = None
    modo_status: Optional[str] = None
    modo_error: Optional[str] = None
    fotocelula_status: Optional[str] = None
    fotocelula_error: Optional[str] = None
    reloj_status: Optional[str] = None
    reloj_error: Optional[str] = None
    horarios_status: Optional[str] = None
    horarios_error: Optional[str] = None
    diagnostico_status: Optional[str] = None
    diagnostico_error: Optional[str] = None
    modfunalu: Optional[int]
    fotocelula_entrada: Optional[bool]
    fotocelula_mem_fun: Optional[bool]
    fotocelula_mem_act: Optional[bool]
    plc_seg: Optional[int]
    plc_min: Optional[int]
    plc_hora: Optional[int]
    plc_dia: Optional[int]
    plc_mes: Optional[int]
    plc_anio: Optional[int]
    plc_diasem: Optional[int]
    cycle_time_error: Optional[bool]
    low_battery: Optional[bool]
    io_verify_error: Optional[bool]


class SeccionEstadoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ciclo_id: int
    timestamp: datetime
    seccion_id: int
    automatico: bool
    manual: bool
    horario_activo: bool


class HorarioTramoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ciclo_id: int
    timestamp: datetime
    tramo_id: int
    inicio_raw: Optional[int]
    fin_raw: Optional[int]


class SeccionHistorialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    seccion_id: int
    automatico: bool
    manual: bool
    horario_activo: bool
