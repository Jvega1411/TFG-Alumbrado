import logging
from datetime import datetime
from typing import Callable

from acquisition.decoders import (
    decode_ar_clock,
    decode_clock_dm,
    decode_i32_low_high,
    decode_modo_label,
    decode_schedule_tramos,
    decode_vector_salidas_logicas,
    extract_section_bits,
    get_bit,
    words,
)
from fins.client import FINSClient
from fins.frame import FINSError
from schemas.blocks import READ_BLOCKS_V3

logger = logging.getLogger(__name__)

CLOCK_DM_ENCODING = "binary"


def read_all_variables(client: FINSClient) -> dict:
    """Lee variables PLC por bloques v3 y conserva datos validos ante fallos parciales."""
    variables = _empty_variables()
    read_status = _empty_read_status()
    raw_cache = _empty_raw_cache()

    for block, reader in READERS:
        _read_block(block, read_status, client, reader, variables.update, raw_cache)

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
        "vector_salidas_logicas": None,
        "contexto_plc_raw": None,
    }


def _empty_read_status() -> dict:
    return {block: {"status": "failed", "error": "no intentado"} for block in READ_BLOCKS_V3}


def _empty_raw_cache() -> dict[str, list[int]]:
    return {}


def _read_block(
    block: str,
    read_status: dict,
    client: FINSClient,
    reader: Callable[[FINSClient, dict], dict],
    apply_result: Callable[[dict], None],
    raw_cache: dict[str, list[int]],
) -> None:
    try:
        apply_result(reader(client, raw_cache))
        read_status[block] = {"status": "ok", "error": None}
    except (FINSError, OSError, ValueError, RuntimeError) as exc:
        read_status[block] = {"status": "failed", "error": str(exc)}
        logger.warning("Fallo lectura FINS bloque %s: %s", block, exc)


def _read_words_cached(
    cache: dict[str, list[int]],
    key: str,
    read_fn: Callable[[int, int], dict],
    start: int,
    count: int,
) -> list[int]:
    if key not in cache:
        cache[key] = words(read_fn(start, count))
    return cache[key]


def _read_secciones(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    raw = _read_words_cached(raw_cache, "H0-H42", client.read_h_range, 0, 43)[11:32]
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
            }
            for i in range(112)
        ],
    }


def _read_modo(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    modfunalu = _read_words_cached(raw_cache, "D100-D116", client.read_dm_range, 100, 17)[16]
    return {"modo": {"modfunalu": modfunalu, "modo_label": decode_modo_label(modfunalu)}}


def _read_fotocelula(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    w25 = _read_words_cached(raw_cache, "W25", client.read_w_range, 25, 1)[0]
    h100 = _read_words_cached(raw_cache, "H100", client.read_h_range, 100, 1)[0]
    dm = _read_words_cached(raw_cache, "D100-D116", client.read_dm_range, 100, 17)[8:16]
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


def _read_reloj(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    raw = _read_words_cached(raw_cache, "D500-D506", client.read_dm_range, 500, 7)
    return {"plc_reloj": decode_clock_dm(raw, encoding=CLOCK_DM_ENCODING)}


def _read_horarios(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    raw_1_2 = _read_words_cached(raw_cache, "D1000-D1007", client.read_dm_range, 1000, 8)
    raw_3_12 = _read_words_cached(raw_cache, "D3630-D3651", client.read_dm_range, 3630, 22)[2:]
    raw_all = raw_1_2 + raw_3_12
    return {"horarios": {"raw_words": raw_all, "tramos": decode_schedule_tramos(raw_all)}}


def _read_diagnostico(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    raw = _read_words_cached(raw_cache, "A401-A402", client.read_ar_range, 401, 2)
    a401 = raw[0]
    a402 = raw[1]
    return {
        "diagnostico": {
            "cycle_time_error": get_bit(a401, 8),
            "low_battery": get_bit(a402, 4),
            "io_verify_error": get_bit(a402, 9),
        }
    }


def _read_reset_temporizado(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    w1_raw = _read_words_cached(raw_cache, "W1", client.read_w_range, 1, 1)[0]
    dm = _read_words_cached(raw_cache, "D100-D116", client.read_dm_range, 100, 17)[2:8]
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


def _read_hmi_original(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    h10 = _read_words_cached(raw_cache, "H0-H42", client.read_h_range, 0, 43)[10]
    dm = _read_words_cached(raw_cache, "D1008-D1009", client.read_dm_range, 1008, 2)
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


def _read_reloj_ar(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    raw = _read_words_cached(raw_cache, "A351-A353", client.read_ar_range, 351, 3)
    return {"reloj_ar": decode_ar_clock(raw[0], raw[1], raw[2])}


def _read_vector_salidas_logicas(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    raw = _read_words_cached(raw_cache, "W4-W13", client.read_w_range, 4, 10)
    return {
        "vector_salidas_logicas": {
            "source_range": "W4-W13",
            "raw_words": raw,
            "bits": decode_vector_salidas_logicas(raw),
        }
    }


def _raw_range(area: str, source_range: str, raw_words: list[int]) -> dict:
    return {
        "area": area,
        "source_range": source_range,
        "raw_words": raw_words,
    }


def _read_contexto_plc_raw(client: FINSClient, raw_cache: dict[str, list[int]]) -> dict:
    return {
        "contexto_plc_raw": {
            "ranges": [
                _raw_range(
                    "H",
                    "H0-H42",
                    _read_words_cached(raw_cache, "H0-H42", client.read_h_range, 0, 43),
                ),
                _raw_range(
                    "H",
                    "H100",
                    _read_words_cached(raw_cache, "H100", client.read_h_range, 100, 1),
                ),
                _raw_range(
                    "W",
                    "W1",
                    _read_words_cached(raw_cache, "W1", client.read_w_range, 1, 1),
                ),
                _raw_range(
                    "W",
                    "W4-W13",
                    _read_words_cached(raw_cache, "W4-W13", client.read_w_range, 4, 10),
                ),
                _raw_range(
                    "W",
                    "W25",
                    _read_words_cached(raw_cache, "W25", client.read_w_range, 25, 1),
                ),
                _raw_range(
                    "D",
                    "D100-D116",
                    _read_words_cached(raw_cache, "D100-D116", client.read_dm_range, 100, 17),
                ),
                _raw_range(
                    "D",
                    "D500-D506",
                    _read_words_cached(raw_cache, "D500-D506", client.read_dm_range, 500, 7),
                ),
                _raw_range(
                    "D",
                    "D1000-D1007",
                    _read_words_cached(raw_cache, "D1000-D1007", client.read_dm_range, 1000, 8),
                ),
                _raw_range(
                    "D",
                    "D1008-D1009",
                    _read_words_cached(raw_cache, "D1008-D1009", client.read_dm_range, 1008, 2),
                ),
                _raw_range(
                    "D",
                    "D3630-D3651",
                    _read_words_cached(raw_cache, "D3630-D3651", client.read_dm_range, 3630, 22),
                ),
                _raw_range(
                    "A",
                    "A351-A353",
                    _read_words_cached(raw_cache, "A351-A353", client.read_ar_range, 351, 3),
                ),
                _raw_range(
                    "A",
                    "A401-A402",
                    _read_words_cached(raw_cache, "A401-A402", client.read_ar_range, 401, 2),
                ),
            ],
        }
    }


READERS: tuple[tuple[str, Callable[[FINSClient, dict], dict]], ...] = (
    ("secciones", _read_secciones),
    ("modo", _read_modo),
    ("fotocelula", _read_fotocelula),
    ("reloj", _read_reloj),
    ("horarios", _read_horarios),
    ("diagnostico", _read_diagnostico),
    ("reset_temporizado", _read_reset_temporizado),
    ("hmi_original", _read_hmi_original),
    ("reloj_ar", _read_reloj_ar),
    ("vector_salidas_logicas", _read_vector_salidas_logicas),
    ("contexto_plc_raw", _read_contexto_plc_raw),
)


def build_payload(ts: datetime, variables: dict) -> dict:
    read_status = variables.get("read_status", _empty_read_status())
    failed = [
        f"{block}: {status['error']}"
        for block, status in read_status.items()
        if status.get("status") != "ok"
    ]
    return {
        "schema_version": 3,
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
        "vector_salidas_logicas": (
            variables["vector_salidas_logicas"]
            if _block_ok(read_status, "vector_salidas_logicas")
            else None
        ),
        "contexto_plc_raw": (
            variables["contexto_plc_raw"] if _block_ok(read_status, "contexto_plc_raw") else None
        ),
    }


def _block_ok(read_status: dict, block: str) -> bool:
    return read_status.get(block, {}).get("status") == "ok"


def build_error_payload(ts: datetime, error: str) -> dict:
    return {
        "schema_version": 3,
        "ts": ts.isoformat(),
        "fins_ok": False,
        "fins_error": error,
        "read_status": {
            block: {"status": "failed", "error": error}
            for block in READ_BLOCKS_V3
        },
        "secciones": [],
    }
