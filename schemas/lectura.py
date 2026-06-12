from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from model.json_columns import load_json_column


def _parse_json_value(value):
    return load_json_column(value)


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
    reset_temporizado_status: Optional[str] = None
    reset_temporizado_error: Optional[str] = None
    hmi_original_status: Optional[str] = None
    hmi_original_error: Optional[str] = None
    reloj_ar_status: Optional[str] = None
    reloj_ar_error: Optional[str] = None
    vector_salidas_logicas_status: Optional[str] = None
    vector_salidas_logicas_error: Optional[str] = None
    contexto_plc_raw_status: Optional[str] = None
    contexto_plc_raw_error: Optional[str] = None
    modfunalu: Optional[int] = None
    modo_label: Optional[str] = None
    fotocelula_entrada: Optional[bool] = None
    fotocelula_mem_fun: Optional[bool] = None
    fotocelula_mem_act: Optional[bool] = None
    plc_seg: Optional[int] = None
    plc_min: Optional[int] = None
    plc_hora: Optional[int] = None
    plc_dia: Optional[int] = None
    plc_mes: Optional[int] = None
    plc_anio: Optional[int] = None
    plc_diasem: Optional[int] = None
    cycle_time_error: Optional[bool] = None
    low_battery: Optional[bool] = None
    io_verify_error: Optional[bool] = None


class SeccionEstadoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ciclo_id: int
    timestamp: datetime
    seccion_id: int
    automatico_calculado: bool
    manual_activo: bool
    salida_interna: bool
    senal_observada_activa: bool
    estado_observable: str


class HorarioTramoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ciclo_id: int
    timestamp: datetime
    tramo_id: int
    inicio_raw: Optional[int] = None
    fin_raw: Optional[int] = None
    inicio_raw_words: Optional[List[int]] = None
    fin_raw_words: Optional[List[int]] = None
    source_json: Optional[Dict[str, str]] = None
    inicio_hora: Optional[int] = None
    inicio_minuto: Optional[int] = None
    fin_hora: Optional[int] = None
    fin_minuto: Optional[int] = None

    @field_validator("inicio_raw_words", "fin_raw_words", "source_json", mode="before")
    @classmethod
    def parse_json_columns(cls, value):
        return _parse_json_value(value)


class SeccionHistorialResponse(SeccionEstadoResponse):
    pass


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
    automatico_calculado: int
    manual_activo: int
    salida_interna: int
    senales_observadas_activas: int
    sin_senal_observada: int


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


class VectorSalidaLogicaBitResponse(BaseModel):
    id: int
    word: str
    bit: int
    source: str
    activa: bool


class VectorSalidasLogicasResponse(BaseModel):
    ciclo_id: int
    source_range: str
    raw_words: List[int]
    bits: List[VectorSalidaLogicaBitResponse]


class ContextoPlcRawRangeResponse(BaseModel):
    area: str
    source_range: str
    raw_words: List[int]


class ContextoPlcRawResponse(BaseModel):
    ciclo_id: int
    ranges: List[ContextoPlcRawRangeResponse]


class FotocelulaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ciclo_id: int
    entrada_raw: bool
    mem_fun: bool
    filtrada_activa: bool
    temporizador_activacion_s: int
    temporizador_desactivacion_s: int
    retardo_activacion_s: int
    retardo_desactivacion_s: int


class ResetTemporizadoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ciclo_id: int
    w1_raw: int
    dm_raw_words: List[int]
    horario_global_activo: bool
    reset_activo: bool
    retardo_segundo_apagado_s: int
    temporizador_segundo_apagado_s: int
    contador_apagados: int
    max_reintentos: int

    @field_validator("dm_raw_words", mode="before")
    @classmethod
    def parse_dm_raw_words(cls, value):
        return _parse_json_value(value)


class HmiOriginalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ciclo_id: int
    indice_seccion: int
    indice_anterior: int
    h10_raw: int
    automatico_seccion_seleccionada: bool
    manual_seccion_seleccionada: bool
    orden_transferencia_comun: bool
    indicacion_activacion_alumbrado_seccion: bool


class RelojArResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ciclo_id: int
    raw_a351: int
    raw_a352: int
    raw_a353: int
    ar_minuto: int
    ar_segundo: int
    ar_dia: int
    ar_hora: int
    ar_anio: int
    ar_mes: int
    encoding: str
