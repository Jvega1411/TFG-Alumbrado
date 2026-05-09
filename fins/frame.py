from typing import Dict, Any, Optional
from config.settings import Config

# Códigos de área para word access según especificación FINS Omron.
# IMPORTANTE: los códigos de bit access (0x30, 0x31, 0x32) son distintos.
# WR=0xB1 y HR=0xB2 confirmados contra PLC real (ver _OLD/SCADA/ROV3.py + CSV outputs).
# CIO=0x30 y AR=0x33 son códigos de bit access — PENDIENTE validar word access en rack.
MEMORY_AREA_CODES = {
    'DM':  0x82,  # Data Memory — word access
    'WR':  0xB1,  # Work area (W) — word access
    'HR':  0xB2,  # Holding area (H) — word access
    'CIO': 0x30,  # PENDIENTE: verificar si es bit o word access para CJ2M
    'AR':  0x33,  # PENDIENTE: verificar si es bit o word access para CJ2M
}


def build_memory_read_frame(
    area: str,
    start_address: int,
    word_count: int,
    config: Optional[Config] = None,
) -> bytes:
    if config is None:
        config = Config

    if area not in MEMORY_AREA_CODES:
        raise ValueError(f"Área '{area}' no válida. Usar: {list(MEMORY_AREA_CODES.keys())}")
    if not (0 <= start_address <= 0xFFFF):
        raise ValueError(f"start_address fuera de rango: {start_address}")
    if not (1 <= word_count <= 999):
        raise ValueError(f"word_count debe estar entre 1-999: {word_count}")

    header = bytes([
        0x80,                        # ICF
        0x00,                        # RSV
        0x02,                        # GCT
        config.FINS_DEST_NETWORK,    # DNA
        config.FINS_DEST_NODE,       # DA1
        config.FINS_DEST_UNIT,       # DA2
        config.FINS_SOURCE_NETWORK,  # SNA
        config.FINS_SOURCE_NODE,     # SA1
        config.FINS_SOURCE_UNIT,     # SA2
        0x00,                        # SID (fijo en construcción; incrementar en cliente si se requiere)
    ])
    command = bytes([0x01, 0x01])  # Memory Area Read
    payload = bytes([
        MEMORY_AREA_CODES[area],
        (start_address >> 8) & 0xFF,
        start_address & 0xFF,
        0x00,                        # bit position — 0x00 para word access
        (word_count >> 8) & 0xFF,
        word_count & 0xFF,
    ])
    return header + command + payload


def parse_fins_response(response: bytes) -> Dict[str, Any]:
    MIN_RESPONSE_LENGTH = 14  # header(10) + command(2) + mres(1) + sres(1)
    if len(response) < MIN_RESPONSE_LENGTH:
        raise ValueError(
            f"Respuesta demasiado corta: {len(response)} bytes (mínimo {MIN_RESPONSE_LENGTH})"
        )

    # Offset-fixed: nunca buscar patrones dentro del payload.
    # [0:10] header, [10:12] command echo, [12] mres, [13] sres, [14:] data
    mres = response[12]
    sres = response[13]
    data_payload = response[14:] if len(response) > 14 else b''

    result: Dict[str, Any] = {'success': mres == 0x00, 'mres': mres, 'sres': sres}
    if result['success']:
        result['data'] = data_payload
        result['word_count'] = len(data_payload) // 2
    else:
        result['error_msg'] = _get_error_message(mres, sres)
    return result


def parse_words_to_int_list(data: bytes) -> list:
    words = []
    for i in range(0, len(data) - 1, 2):
        words.append((data[i] << 8) | data[i + 1])
    return words


def _get_error_message(mres: int, sres: int) -> str:
    MRES_MESSAGES = {
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
        0x21: "Read-only mode",
    }
    base_msg = MRES_MESSAGES.get(mres, "Unknown error")
    return f"MRES=0x{mres:02X} SRES=0x{sres:02X}: {base_msg}"
