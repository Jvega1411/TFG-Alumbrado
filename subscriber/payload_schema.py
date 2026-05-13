import json
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


class ReadBlockStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "failed", "absent"]
    error: Optional[str] = None


class SeccionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrictInt
    automatico: StrictBool
    manual: StrictBool
    horario_activo: StrictBool


class RelojPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seg: StrictInt
    min: StrictInt
    hora: StrictInt
    dia: StrictInt
    mes: StrictInt
    anio: StrictInt
    diasem: StrictInt


class ModoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modfunalu: StrictInt
    fotocelula_entrada: StrictBool
    fotocelula_mem_fun: StrictBool
    fotocelula_mem_act: StrictBool


class HorariosPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # PENDIENTE P1: longitud y semantica real se confirmaran con smoke FINS.
    raw_words: List[StrictInt] = Field(default_factory=list)


class DiagnosticoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_time_error: StrictBool
    low_battery: StrictBool
    io_verify_error: StrictBool


class MQTTPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Optional[StrictInt] = None
    ts: datetime
    fins_ok: StrictBool
    fins_error: Optional[str] = None
    read_status: Optional[Dict[str, ReadBlockStatus]] = None
    plc_reloj: Optional[RelojPayload] = None
    modo: Optional[ModoPayload] = None
    secciones: List[SeccionPayload] = Field(default_factory=list)
    horarios: Optional[HorariosPayload] = None
    diagnostico: Optional[DiagnosticoPayload] = None

    @model_validator(mode="after")
    def validate_secciones_when_block_ok(self) -> "MQTTPayload":
        if self.block_ok("secciones"):
            if len(self.secciones) != 112:
                raise ValueError(
                    f"bloque secciones ok requiere exactamente 112 secciones, recibidas: {len(self.secciones)}"
                )
            ids = [s.id for s in self.secciones]
            if len(set(ids)) != 112:
                raise ValueError("IDs de secciones duplicados en el payload")
            if sorted(ids) != list(range(1, 113)):
                raise ValueError("IDs de secciones deben ser 1..112")
        return self

    def block_status(self, block: str) -> Optional[str]:
        if self.read_status is not None:
            rs = self.read_status.get(block)
            return rs.status if rs is not None else None
        return "ok" if self.fins_ok else "failed"

    def block_error(self, block: str) -> Optional[str]:
        if self.read_status is not None:
            rs = self.read_status.get(block)
            return rs.error if rs is not None else None
        return None if self.fins_ok else self.fins_error

    def block_ok(self, block: str) -> bool:
        if self.read_status is not None:
            rs = self.read_status.get(block)
            return rs is not None and rs.status == "ok"
        return self.fins_ok


def parse_payload(payload_bytes: bytes) -> MQTTPayload:
    """Decode and validate a MQTT payload."""
    try:
        text = payload_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"UTF-8 decode error: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc}") from exc
    return MQTTPayload.model_validate(data)
