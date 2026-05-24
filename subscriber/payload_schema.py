import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from schemas.blocks import READ_BLOCKS_V2

Word = Annotated[StrictInt, Field(ge=0, le=0xFFFF)]
Int32 = Annotated[StrictInt, Field(ge=-(2**31), le=2**31 - 1)]
SectionId = Annotated[StrictInt, Field(ge=1, le=112)]
CerchaId = Annotated[StrictInt, Field(ge=1, le=160)]
TramoId = Annotated[StrictInt, Field(ge=1, le=12)]
Hour = Annotated[StrictInt, Field(ge=0, le=23)]
MinuteSecond = Annotated[StrictInt, Field(ge=0, le=59)]
Day = Annotated[StrictInt, Field(ge=1, le=31)]
Month = Annotated[StrictInt, Field(ge=1, le=12)]
Year2 = Annotated[StrictInt, Field(ge=0, le=99)]
DayOfWeek = Annotated[StrictInt, Field(ge=0, le=7)]

FixedLen2 = Annotated[list[Word], Field(min_length=2, max_length=2)]
FixedLen6 = Annotated[list[Word], Field(min_length=6, max_length=6)]
FixedLen7 = Annotated[list[Word], Field(min_length=7, max_length=7)]
FixedLen10 = Annotated[list[Word], Field(min_length=10, max_length=10)]
FixedLen28 = Annotated[list[Word], Field(min_length=28, max_length=28)]


def _bcd_byte_to_int(byte: int) -> int:
    high = (byte >> 4) & 0x0F
    low = byte & 0x0F
    if high > 9 or low > 9:
        raise ValueError(f"byte no BCD: 0x{byte & 0xFF:02X}")
    return high * 10 + low


def _modo_label(modfunalu: int) -> str:
    return {
        0: "horarios",
        1: "fotocelula",
        2: "ambos",
    }.get(modfunalu, "desconocido")


class ReadBlockStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "failed"]
    error: str | None = None

    @model_validator(mode="after")
    def validate_error(self) -> "ReadBlockStatus":
        if self.status == "ok" and self.error is not None:
            raise ValueError("status ok requiere error=None")
        if self.status == "failed" and (self.error is None or not self.error.strip()):
            raise ValueError("status failed requiere error")
        return self


class SeccionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: SectionId
    automatico_calculado: StrictBool
    manual_activo: StrictBool
    salida_interna: StrictBool
    salida_wr: StrictBool | None = None


class ModoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modfunalu: Word
    modo_label: Literal["horarios", "fotocelula", "ambos", "desconocido"]

    @model_validator(mode="after")
    def validate_label(self) -> "ModoPayload":
        expected = _modo_label(self.modfunalu)
        if self.modo_label != expected:
            raise ValueError(f"modo_label incoherente: esperado {expected}")
        return self


class FotocelulaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entrada_raw: StrictBool
    entrada_raw_source: Literal["W25.00"]
    mem_fun: StrictBool
    mem_fun_source: Literal["H100.00"]
    filtrada_activa: StrictBool
    filtrada_source: Literal["H100.01"]
    temporizador_activacion_s: Int32
    temporizador_desactivacion_s: Int32
    retardo_activacion_s: Int32
    retardo_desactivacion_s: Int32


class RelojDecoded(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segundo: MinuteSecond
    minuto: MinuteSecond
    hora: Hour
    dia: Day
    mes: Month
    anio: Year2
    dia_semana: DayOfWeek


class RelojPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_words: FixedLen7
    encoding: Literal["binary", "bcd"]
    decoded: RelojDecoded

    @model_validator(mode="after")
    def validate_decoded_matches_raw(self) -> "RelojPayload":
        if self.encoding == "binary":
            values = self.raw_words
        else:
            values = [_bcd_byte_to_int(word & 0xFF) for word in self.raw_words]
        expected = {
            "segundo": values[0],
            "minuto": values[1],
            "hora": values[2],
            "dia": values[3],
            "mes": values[4],
            "anio": values[5],
            "dia_semana": values[6],
        }
        if self.decoded.model_dump() != expected:
            raise ValueError("reloj.decoded no coincide con raw_words")
        return self


class TramoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tramo: TramoId
    inicio_hora: Hour | None
    inicio_minuto: MinuteSecond | None
    fin_hora: Hour
    fin_minuto: MinuteSecond
    inicio_raw: FixedLen2 | None = None
    fin_raw: FixedLen2
    source: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_raw_and_source(self) -> "TramoPayload":
        if self.tramo in (1, 2):
            if self.inicio_hora is None or self.inicio_minuto is None or self.inicio_raw is None:
                raise ValueError("tramos 1..2 requieren inicio")
            expected_source = {
                "inicio_hora": f"D{1000 + (self.tramo - 1) * 4}",
                "inicio_minuto": f"D{1001 + (self.tramo - 1) * 4}",
                "fin_hora": f"D{1002 + (self.tramo - 1) * 4}",
                "fin_minuto": f"D{1003 + (self.tramo - 1) * 4}",
            }
            if self.inicio_raw != [self.inicio_hora, self.inicio_minuto]:
                raise ValueError("inicio_raw no coincide con inicio_hora/inicio_minuto")
        else:
            expected_source = {
                "fin_hora": f"D{3632 + (self.tramo - 3) * 2}",
                "fin_minuto": f"D{3633 + (self.tramo - 3) * 2}",
            }
            if self.inicio_hora is not None or self.inicio_minuto is not None or self.inicio_raw is not None:
                raise ValueError("tramos 3..12 no tienen inicio confirmado")
        if self.fin_raw != [self.fin_hora, self.fin_minuto]:
            raise ValueError("fin_raw no coincide con fin_hora/fin_minuto")
        if self.source != expected_source:
            raise ValueError("source de horario no coincide con tramo")
        return self


class HorariosPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_words: FixedLen28
    tramos: Annotated[list[TramoPayload], Field(min_length=12, max_length=12)]


class DiagnosticoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_time_error: StrictBool
    low_battery: StrictBool
    io_verify_error: StrictBool


class ResetSubPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activo: StrictBool
    activo_source: Literal["W1.02"]
    retardo_segundo_apagado_s: Int32
    temporizador_segundo_apagado_s: Int32
    contador_apagados: Word
    max_reintentos: Literal[3] = 3


class ResetTemporizadoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    w1_raw: Word
    dm_raw_words: FixedLen6
    horario_global_activo: StrictBool
    horario_global_activo_source: Literal["W1.01"]
    reset: ResetSubPayload


class HmiOriginalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indice_seccion: Annotated[StrictInt, Field(ge=0, le=111)]
    indice_anterior: Annotated[StrictInt, Field(ge=0, le=111)]
    automatico_seccion_seleccionada: StrictBool
    manual_seccion_seleccionada: StrictBool
    orden_transferencia_comun: StrictBool
    indicacion_activacion_alumbrado_seccion: StrictBool
    h10_raw: Word


class RelojArRaw(BaseModel):
    model_config = ConfigDict(extra="forbid")

    A351_minsegplc: Word
    A352_diahorplc: Word
    A353_anomesplc: Word


class RelojArDecoded(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minuto: MinuteSecond
    segundo: MinuteSecond
    dia: Day
    hora: Hour
    anio: Year2
    mes: Month


class RelojArPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw: RelojArRaw
    decoded: RelojArDecoded
    encoding: Literal["bcd_packed_channel"]

    @model_validator(mode="after")
    def validate_decoded_matches_raw(self) -> "RelojArPayload":
        expected = {
            "minuto": _bcd_byte_to_int((self.raw.A351_minsegplc >> 8) & 0xFF),
            "segundo": _bcd_byte_to_int(self.raw.A351_minsegplc & 0xFF),
            "dia": _bcd_byte_to_int((self.raw.A352_diahorplc >> 8) & 0xFF),
            "hora": _bcd_byte_to_int(self.raw.A352_diahorplc & 0xFF),
            "anio": _bcd_byte_to_int((self.raw.A353_anomesplc >> 8) & 0xFF),
            "mes": _bcd_byte_to_int(self.raw.A353_anomesplc & 0xFF),
        }
        if self.decoded.model_dump() != expected:
            raise ValueError("reloj_ar.decoded no coincide con raw")
        return self


class CerchaSalidaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: CerchaId
    activa: StrictBool
    source: str
    physical_io_confirmed: Literal[False] = False

    @model_validator(mode="after")
    def validate_source(self) -> "CerchaSalidaPayload":
        idx = self.id - 1
        expected = f"W{4 + idx // 16}.{idx % 16:02d}"
        if self.source != expected:
            raise ValueError(f"source incoherente para cercha {self.id}: esperado {expected}")
        return self


class SalidasWrPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_words: FixedLen10
    cercha_salidas: Annotated[list[CerchaSalidaPayload], Field(min_length=160, max_length=160)]
    physical_io_mapping_status: Literal["pending_cio_map"]


class LecturaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2]
    ts: datetime
    fins_ok: StrictBool
    fins_error: str | None = None
    read_status: dict[str, ReadBlockStatus]
    modo: ModoPayload | None = None
    fotocelula: FotocelulaPayload | None = None
    plc_reloj: RelojPayload | None = None
    horarios: HorariosPayload | None = None
    diagnostico: DiagnosticoPayload | None = None
    reset_temporizado: ResetTemporizadoPayload | None = None
    hmi_original: HmiOriginalPayload | None = None
    reloj_ar: RelojArPayload | None = None
    secciones: list[SeccionPayload] = Field(default_factory=list)
    salidas_wr: SalidasWrPayload | None = None

    @model_validator(mode="after")
    def validate_status_keys(self) -> "LecturaPayload":
        expected = set(READ_BLOCKS_V2)
        received = set(self.read_status)
        if received != expected:
            raise ValueError(
                "read_status v2 requiere exactamente: " + ", ".join(READ_BLOCKS_V2)
            )
        return self

    @model_validator(mode="after")
    def validate_timestamp(self) -> "LecturaPayload":
        if self.ts.tzinfo is None or self.ts.utcoffset() is None:
            raise ValueError("ts requiere timezone explicito")
        return self

    @model_validator(mode="after")
    def validate_fins_ok(self) -> "LecturaPayload":
        all_ok = all(status.status == "ok" for status in self.read_status.values())
        if self.fins_ok != all_ok:
            raise ValueError("fins_ok incoherente con read_status")
        if self.fins_ok and self.fins_error is not None:
            raise ValueError("fins_ok=True requiere fins_error=None")
        if not self.fins_ok and (self.fins_error is None or not self.fins_error.strip()):
            raise ValueError("fins_ok=False requiere fins_error")
        return self

    @model_validator(mode="after")
    def validate_payload_by_block(self) -> "LecturaPayload":
        def ok(block: str) -> bool:
            return self.read_status[block].status == "ok"

        if ok("secciones"):
            ids = sorted(section.id for section in self.secciones)
            if ids != list(range(1, 113)):
                raise ValueError("secciones ok requiere ids 1..112")
        elif self.secciones:
            raise ValueError("secciones failed no acepta datos")

        pairs = (
            ("modo", self.modo),
            ("fotocelula", self.fotocelula),
            ("reloj", self.plc_reloj),
            ("horarios", self.horarios),
            ("diagnostico", self.diagnostico),
            ("reset_temporizado", self.reset_temporizado),
            ("hmi_original", self.hmi_original),
            ("reloj_ar", self.reloj_ar),
            ("salidas_wr", self.salidas_wr),
        )
        for block, payload in pairs:
            if ok(block) and payload is None:
                raise ValueError(f"bloque {block} ok requiere payload")
            if not ok(block) and payload is not None:
                raise ValueError(f"bloque {block} failed no acepta payload")

        if ok("horarios"):
            tramos = sorted(tramo.tramo for tramo in self.horarios.tramos)
            if tramos != list(range(1, 13)):
                raise ValueError("horarios ok requiere tramos 1..12")

        if ok("salidas_wr"):
            ids = sorted(row.id for row in self.salidas_wr.cercha_salidas)
            if ids != list(range(1, 161)):
                raise ValueError("salidas_wr ok requiere ids 1..160")

        if ok("secciones") and not ok("salidas_wr"):
            if any(section.salida_wr is not None for section in self.secciones):
                raise ValueError("salidas_wr failed requiere seccion.salida_wr=None")

        if ok("secciones") and ok("salidas_wr"):
            by_id = {row.id: row.activa for row in self.salidas_wr.cercha_salidas}
            for section in self.secciones:
                if section.salida_wr is None:
                    raise ValueError("secciones+salidas_wr ok requiere salida_wr")
                if section.salida_wr != by_id[section.id]:
                    raise ValueError("seccion.salida_wr no coincide con salidas_wr")

        return self

    def block_status(self, block: str) -> str:
        return self.read_status[block].status

    def block_error(self, block: str) -> str | None:
        return self.read_status[block].error

    def block_ok(self, block: str) -> bool:
        return self.block_status(block) == "ok"


MQTTPayload = LecturaPayload


def parse_payload(payload_bytes: bytes) -> LecturaPayload:
    """Decode and validate a MQTT v2 payload."""
    try:
        text = payload_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"UTF-8 decode error: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc}") from exc
    return LecturaPayload.model_validate(data)
