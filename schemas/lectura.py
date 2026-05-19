from datetime import datetime
from typing import Dict, Optional

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


class DashboardCapabilitiesResponse(BaseModel):
    mode: str
    can_write: bool
    write_mode_available: bool
    auth_required_for_write: bool


class DashboardBlockStatusResponse(BaseModel):
    status: Optional[str] = None
    error: Optional[str] = None


class DashboardSectionCountersResponse(BaseModel):
    total: int
    con_dato: int
    automatico: int
    manual: int
    horario_activo: int
    apagadas: int


class DashboardPlcRelojResponse(BaseModel):
    seg: Optional[int] = None
    min: Optional[int] = None
    hora: Optional[int] = None
    dia: Optional[int] = None
    mes: Optional[int] = None
    anio: Optional[int] = None
    diasem: Optional[int] = None


class DashboardDiagnosticFlagsResponse(BaseModel):
    cycle_time_error: Optional[bool] = None
    low_battery: Optional[bool] = None
    io_verify_error: Optional[bool] = None


class DashboardFreshnessResponse(BaseModel):
    generated_at: datetime
    timestamp_rpi: Optional[datetime] = None
    age_seconds: Optional[int] = None
    stale_after_seconds: int
    is_stale: bool


class DashboardResumenResponse(BaseModel):
    timestamp_rpi: Optional[datetime] = None
    plc_reloj: Optional[DashboardPlcRelojResponse] = None
    fins_ok: bool
    fins_error: Optional[str] = None
    bloques: Dict[str, DashboardBlockStatusResponse]
    secciones: DashboardSectionCountersResponse
    diagnostico: DashboardDiagnosticFlagsResponse
    frescura: DashboardFreshnessResponse
    capabilities: DashboardCapabilitiesResponse
