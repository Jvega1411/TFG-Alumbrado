from typing import Any, Dict, Optional

from config.settings import Config

# Codigos de area FINS para word access. No usar los codigos bit access
# 0x30-0x33 cuando se pretende leer words y desempaquetar bits en software.
MEMORY_AREA_CODES = {
    "DM": 0x82,   # Data Memory, word access
    "WR": 0xB1,   # Work Relay, word access
    "HR": 0xB2,   # Holding Relay, word access
    "CIO": 0xB0,  # CIO, word access
    "AR": 0xB3,   # Auxiliary Relay, word access
}


class FINSError(Exception):
    """Base para errores especificos de FINS."""


class FINSResponseError(FINSError):
    """Respuesta FINS valida con codigo MRES/SRES no exitoso."""

    def __init__(self, mres: int, sres: int):
        self.mres = mres
        self.sres = sres
        super().__init__(_get_error_message(mres, sres))


class PLCNotInRunError(FINSResponseError):
    """Condicion operacional: el PLC no esta en RUN para la lectura solicitada."""


class FINSProtocolError(FINSError, ValueError):
    """Respuesta FINS malformada, truncada o no correlacionada."""


def build_memory_read_frame(
    area: str,
    start_address: int,
    word_count: int,
    config: Optional[Config] = None,
    sid: int = 0,
) -> bytes:
    if config is None:
        config = Config

    if area not in MEMORY_AREA_CODES:
        raise ValueError(f"Area '{area}' no valida. Usar: {list(MEMORY_AREA_CODES.keys())}")
    if not (0 <= start_address <= 0xFFFF):
        raise ValueError(f"start_address fuera de rango: {start_address}")
    if not (1 <= word_count <= 999):
        raise ValueError(f"word_count debe estar entre 1-999: {word_count}")
    if not (0 <= sid <= 0xFF):
        raise ValueError(f"sid fuera de rango: {sid}")

    header = bytes([
        0x80,                        # ICF: command, response required
        0x00,                        # RSV
        0x02,                        # GCT
        config.FINS_DEST_NETWORK,    # DNA
        config.FINS_DEST_NODE,       # DA1
        config.FINS_DEST_UNIT,       # DA2
        config.FINS_SOURCE_NETWORK,  # SNA
        config.FINS_SOURCE_NODE,     # SA1
        config.FINS_SOURCE_UNIT,     # SA2
        sid,                         # SID
    ])
    command = bytes([0x01, 0x01])  # Memory Area Read
    payload = bytes([
        MEMORY_AREA_CODES[area],
        (start_address >> 8) & 0xFF,
        start_address & 0xFF,
        0x00,  # bit position: word access
        (word_count >> 8) & 0xFF,
        word_count & 0xFF,
    ])
    return header + command + payload


def parse_fins_response(
    response: bytes,
    *,
    expected_sid: Optional[int] = None,
    expected_word_count: Optional[int] = None,
    raise_on_error: bool = False,
) -> Dict[str, Any]:
    min_response_length = 14  # header(10) + command echo(2) + MRES/SRES(2)
    if len(response) < min_response_length:
        raise FINSProtocolError(
            f"Respuesta demasiado corta: {len(response)} bytes (minimo {min_response_length})"
        )

    sid_echo = response[9]
    command_echo = response[10:12]
    mres = response[12]
    sres = response[13]
    data_payload = response[14:]

    if expected_sid is not None and sid_echo != expected_sid:
        raise FINSProtocolError(
            f"SID inesperado: recibido 0x{sid_echo:02X}, esperado 0x{expected_sid:02X}"
        )
    if command_echo != b"\x01\x01":
        raise FINSProtocolError(f"Command echo inesperado: {command_echo.hex()}")
    success = mres == 0x00 and sres == 0x00
    result: Dict[str, Any] = {"success": success, "mres": mres, "sres": sres}
    if success:
        if len(data_payload) % 2 != 0:
            raise FINSProtocolError(f"Payload de longitud impar: {len(data_payload)} bytes")
        if expected_word_count is not None and len(data_payload) != expected_word_count * 2:
            raise FINSProtocolError(
                f"Payload truncado o sobrante: {len(data_payload)} bytes "
                f"para {expected_word_count} words"
            )
        result["data"] = data_payload
        result["word_count"] = len(data_payload) // 2
    else:
        result["error_msg"] = _get_error_message(mres, sres)
        if raise_on_error:
            if (mres, sres) == (0x21, 0x08):
                raise PLCNotInRunError(mres, sres)
            raise FINSResponseError(mres, sres)
    return result


def parse_words_to_int_list(data: bytes) -> list[int]:
    if len(data) % 2 != 0:
        raise FINSProtocolError(f"Payload de longitud impar: {len(data)} bytes")
    return [(data[i] << 8) | data[i + 1] for i in range(0, len(data), 2)]


def _get_error_message(mres: int, sres: int) -> str:
    messages = {
        0x00: "Success",
        0x01: "Service canceled",
        0x03: "Local node error",
        0x04: "Destination node error",
        0x05: "Communications controller error",
        0x10: "CPU Unit error",
        0x11: "Command format error",
        0x13: "Memory area not available",
        0x15: "Access size error",
        0x18: "CPU Unit busy",
        0x1A: "Data error",
        0x21: "CPU Unit status/error",
    }
    base_msg = messages.get(mres, "Unknown error")
    return f"MRES=0x{mres:02X} SRES=0x{sres:02X}: {base_msg}"
