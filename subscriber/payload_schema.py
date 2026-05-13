import json
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


EXPECTED_READ_STATUS_BLOCKS = ("secciones", "modo", "fotocelula", "reloj", "horarios", "diagnostico")


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

    modfunalu: Optional[StrictInt] = None
    fotocelula_entrada: Optional[StrictBool] = None
    fotocelula_mem_fun: Optional[StrictBool] = None
    fotocelula_mem_act: Optional[StrictBool] = None


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
    def validate_blocks_when_ok(self) -> "MQTTPayload":
        if self.read_status is not None:
            expected = set(EXPECTED_READ_STATUS_BLOCKS)
            received = set(self.read_status)
            if received != expected:
                raise ValueError(
                    "read_status requiere exactamente bloques: "
                    + ", ".join(EXPECTED_READ_STATUS_BLOCKS)
                )

        if self.read_status is not None:
            all_blocks_ok = all(block.status == "ok" for block in self.read_status.values())
            if self.fins_ok != all_blocks_ok:
                raise ValueError("fins_ok incoherente con read_status")

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
        if self.block_ok("modo") and (self.modo is None or self.modo.modfunalu is None):
            raise ValueError("bloque modo ok requiere modo.modfunalu")
        if self.block_ok("fotocelula") and (
            self.modo is None
            or self.modo.fotocelula_entrada is None
            or self.modo.fotocelula_mem_fun is None
            or self.modo.fotocelula_mem_act is None
        ):
            raise ValueError("bloque fotocelula ok requiere campos de fotocelula en modo")
        if self.block_ok("reloj") and self.plc_reloj is None:
            raise ValueError("bloque reloj ok requiere plc_reloj")
        if self.block_ok("diagnostico") and self.diagnostico is None:
            raise ValueError("bloque diagnostico ok requiere diagnostico")
        if self.block_ok("horarios"):
            if self.horarios is None:
                raise ValueError("bloque horarios ok requiere horarios")
            if len(self.horarios.raw_words) < 24:
                raise ValueError("bloque horarios ok requiere al menos 24 raw_words")
        self._reject_failed_block_data()
        return self

    def _reject_failed_block_data(self) -> None:
        if self.block_status("secciones") in {"failed", "absent"} and self.secciones:
            raise ValueError("bloque secciones failed/absent no acepta datos de secciones")
        if self.modo is not None:
            if self.block_status("modo") in {"failed", "absent"} and self.modo.modfunalu is not None:
                raise ValueError("bloque modo failed/absent no acepta modo.modfunalu")
            if self.block_status("fotocelula") in {"failed", "absent"} and (
                self.modo.fotocelula_entrada is not None
                or self.modo.fotocelula_mem_fun is not None
                or self.modo.fotocelula_mem_act is not None
            ):
                raise ValueError("bloque fotocelula failed/absent no acepta campos de fotocelula")
        if self.block_status("reloj") in {"failed", "absent"} and self.plc_reloj is not None:
            raise ValueError("bloque reloj failed/absent no acepta plc_reloj")
        if self.block_status("horarios") in {"failed", "absent"} and self.horarios is not None:
            raise ValueError("bloque horarios failed/absent no acepta horarios")
        if self.block_status("diagnostico") in {"failed", "absent"} and self.diagnostico is not None:
            raise ValueError("bloque diagnostico failed/absent no acepta diagnostico")

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
