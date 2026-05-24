import logging
from datetime import datetime
from typing import Callable

from acquisition.decoders import (
    decode_ar_clock,
    decode_cercha_salidas,
    decode_clock_dm,
    decode_i32_low_high,
    decode_modo_label,
    decode_schedule_tramos,
    extract_section_bits,
    get_bit,
    words,
)
from fins.client import FINSClient
from fins.frame import FINSError
from schemas.blocks import READ_BLOCKS, READ_BLOCKS_V2

logger = logging.getLogger(__name__)

CLOCK_DM_ENCODING = "binary"


def read_all_variables(client: FINSClient) -> dict:
    """Lee variables PLC por bloques v2 y conserva datos validos ante fallos parciales."""
    variables = _empty_variables()
    read_status = _empty_read_status()

    _read_block("secciones", read_status, lambda: _read_secciones(client), lambda v: variables.update(v))
    _read_block("modo", read_status, lambda: _read_modo(client), lambda v: variables.update(v))
    _read_block("fotocelula", read_status, lambda: _read_fotocelula(client), lambda v: variables.update(v))
    _read_block("reloj", read_status, lambda: _read_reloj(client), lambda v: variables.update(v))
    _read_block("horarios", read_status, lambda: _read_horarios(client), lambda v: variables.update(v))
    _read_block("diagnostico", read_status, lambda: _read_diagnostico(client), lambda v: variables.update(v))
    _read_block(
        "reset_temporizado",
        read_status,
        lambda: _read_reset_temporizado(client),
        lambda v: variables.update(v),
    )
    _read_block("hmi_original", read_status, lambda: _read_hmi_original(client), lambda v: variables.update(v))
    _read_block("reloj_ar", read_status, lambda: _read_reloj_ar(client), lambda v: variables.update(v))
    _read_block("salidas_wr", read_status, lambda: _read_salidas_wr(client), lambda v: variables.update(v))

    _attach_salida_wr(variables, read_status)
    variables["read_status"] = read_status
    return variables


def _empty_variables() -> dict:
    return {
        "secciones": [],
        "modo": None,
        "fotocelula": None,
        "plc_reloj": None,
        "horarios": None,
        "diagnostico": None,
        "reset_temporizado": None,
        "hmi_original": None,
        "reloj_ar": None,
        "salidas_wr": None,
    }


def _empty_read_status() -> dict:
    return {block: {"status": "failed", "error": "no intentado"} for block in READ_BLOCKS_V2}


def _read_block(
    block: str,
    read_status: dict,
    reader: Callable[[], dict],
    apply_result: Callable[[dict], None],
) -> None:
    try:
        apply_result(reader())
        read_status[block] = {"status": "ok", "error": None}
    except (FINSError, OSError, ValueError, RuntimeError) as exc:
        read_status[block] = {"status": "failed", "error": str(exc)}
        logger.warning("Fallo lectura FINS bloque %s: %s", block, exc)


def _read_secciones(client: FINSClient) -> dict:
    raw = words(client.read_h_range(11, 21))
    automaticos = extract_section_bits(raw, 0)
    manuales = extract_section_bits(raw, 7)
    salida_interna = extract_section_bits(raw, 14)
    return {
        "secciones": [
            {
                "id": i + 1,
                "automatico_calculado": automaticos[i],
                "manual_activo": manuales[i],
                "salida_interna": salida_interna[i],
                "salida_wr": None,
            }
            for i in range(112)
        ],
    }


def _read_modo(client: FINSClient) -> dict:
    modfunalu = words(client.read_dm_range(116, 1))[0]
    return {"modo": {"modfunalu": modfunalu, "modo_label": decode_modo_label(modfunalu)}}


def _read_fotocelula(client: FINSClient) -> dict:
    w25 = words(client.read_w_range(25, 1))[0]
    h100 = words(client.read_h_range(100, 1))[0]
    dm = words(client.read_dm_range(108, 8))
    return {
        "fotocelula": {
            "entrada_raw": get_bit(w25, 0),
            "entrada_raw_source": "W25.00",
            "mem_fun": get_bit(h100, 0),
            "mem_fun_source": "H100.00",
            "filtrada_activa": get_bit(h100, 1),
            "filtrada_source": "H100.01",
            "temporizador_activacion_s": decode_i32_low_high(dm[0], dm[1]),
            "temporizador_desactivacion_s": decode_i32_low_high(dm[2], dm[3]),
            "retardo_activacion_s": decode_i32_low_high(dm[4], dm[5]),
            "retardo_desactivacion_s": decode_i32_low_high(dm[6], dm[7]),
        }
    }


def _read_reloj(client: FINSClient) -> dict:
    raw = words(client.read_dm_range(500, 7))
    return {"plc_reloj": decode_clock_dm(raw, encoding=CLOCK_DM_ENCODING)}


def _read_horarios(client: FINSClient) -> dict:
    raw_1_2 = words(client.read_dm_range(1000, 8))
    raw_3_12 = words(client.read_dm_range(3632, 20))
    raw_all = raw_1_2 + raw_3_12
    return {"horarios": {"raw_words": raw_all, "tramos": decode_schedule_tramos(raw_all)}}


def _read_diagnostico(client: FINSClient) -> dict:
    a401 = words(client.read_ar_range(401, 1))[0]
    a402 = words(client.read_ar_range(402, 1))[0]
    return {
        "diagnostico": {
            "cycle_time_error": get_bit(a401, 8),
            "low_battery": get_bit(a402, 4),
            "io_verify_error": get_bit(a402, 9),
        }
    }


def _read_reset_temporizado(client: FINSClient) -> dict:
    w1_raw = words(client.read_w_range(1, 1))[0]
    dm = words(client.read_dm_range(102, 6))
    return {
        "reset_temporizado": {
            "w1_raw": w1_raw,
            "dm_raw_words": dm,
            "horario_global_activo": get_bit(w1_raw, 1),
            "horario_global_activo_source": "W1.01",
            "reset": {
                "activo": get_bit(w1_raw, 2),
                "activo_source": "W1.02",
                "retardo_segundo_apagado_s": decode_i32_low_high(dm[0], dm[1]),
                "temporizador_segundo_apagado_s": decode_i32_low_high(dm[2], dm[3]),
                "contador_apagados": dm[4],
                "max_reintentos": 3,
            },
        }
    }


def _read_hmi_original(client: FINSClient) -> dict:
    h10 = words(client.read_h_range(10, 1))[0]
    dm = words(client.read_dm_range(1008, 2))
    return {
        "hmi_original": {
            "indice_seccion": dm[0],
            "indice_anterior": dm[1],
            "automatico_seccion_seleccionada": get_bit(h10, 12),
            "manual_seccion_seleccionada": get_bit(h10, 13),
            "orden_transferencia_comun": get_bit(h10, 14),
            "indicacion_activacion_alumbrado_seccion": get_bit(h10, 15),
            "h10_raw": h10,
        }
    }


def _read_reloj_ar(client: FINSClient) -> dict:
    raw = words(client.read_ar_range(351, 3))
    return {"reloj_ar": decode_ar_clock(raw[0], raw[1], raw[2])}


def _read_salidas_wr(client: FINSClient) -> dict:
    raw = words(client.read_w_range(4, 10))
    return {
        "salidas_wr": {
            "raw_words": raw,
            "cercha_salidas": decode_cercha_salidas(raw),
            "physical_io_mapping_status": "pending_cio_map",
        }
    }


def _attach_salida_wr(variables: dict, read_status: dict) -> None:
    if read_status["secciones"]["status"] != "ok":
        return
    if read_status["salidas_wr"]["status"] != "ok" or variables["salidas_wr"] is None:
        for seccion in variables["secciones"]:
            seccion["salida_wr"] = None
        return
    by_id = {row["id"]: row["activa"] for row in variables["salidas_wr"]["cercha_salidas"]}
    for seccion in variables["secciones"]:
        seccion["salida_wr"] = by_id.get(seccion["id"])


def build_payload(ts: datetime, variables: dict) -> dict:
    read_status = variables.get("read_status", _empty_read_status())
    failed = [
        f"{block}: {status['error']}"
        for block, status in read_status.items()
        if status.get("status") != "ok"
    ]
    return {
        "schema_version": 2,
        "ts": ts.isoformat(),
        "fins_ok": not failed,
        "fins_error": None if not failed else "Bloques FINS fallidos: " + "; ".join(failed),
        "read_status": read_status,
        "modo": variables["modo"] if _block_ok(read_status, "modo") else None,
        "fotocelula": variables["fotocelula"] if _block_ok(read_status, "fotocelula") else None,
        "plc_reloj": variables["plc_reloj"] if _block_ok(read_status, "reloj") else None,
        "horarios": variables["horarios"] if _block_ok(read_status, "horarios") else None,
        "diagnostico": variables["diagnostico"] if _block_ok(read_status, "diagnostico") else None,
        "reset_temporizado": (
            variables["reset_temporizado"] if _block_ok(read_status, "reset_temporizado") else None
        ),
        "hmi_original": variables["hmi_original"] if _block_ok(read_status, "hmi_original") else None,
        "reloj_ar": variables["reloj_ar"] if _block_ok(read_status, "reloj_ar") else None,
        "secciones": variables["secciones"] if _block_ok(read_status, "secciones") else [],
        "salidas_wr": variables["salidas_wr"] if _block_ok(read_status, "salidas_wr") else None,
    }


def _block_ok(read_status: dict, block: str) -> bool:
    return read_status.get(block, {}).get("status") == "ok"


def build_error_payload(ts: datetime, error: str) -> dict:
    return {
        "schema_version": 2,
        "ts": ts.isoformat(),
        "fins_ok": False,
        "fins_error": error,
        "read_status": {
            block: {"status": "failed", "error": error}
            for block in READ_BLOCKS_V2
        },
        "secciones": [],
    }
