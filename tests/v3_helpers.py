import json
from datetime import datetime, timezone

from acquisition.decoders import decode_schedule_tramos, decode_vector_salidas_logicas
from schemas.blocks import READ_BLOCKS_V3


def make_words_bytes(words: list[int]) -> bytes:
    result = b""
    for word in words:
        result += bytes([(word >> 8) & 0xFF, word & 0xFF])
    return result


def make_fins_response(words: list[int]) -> dict:
    return {
        "success": True,
        "mres": 0,
        "sres": 0,
        "data": make_words_bytes(words),
        "word_count": len(words),
    }


def read_status(failed: set[str] | None = None) -> dict:
    failed = failed or set()
    return {
        block: (
            {"status": "failed", "error": f"timeout {block}"}
            if block in failed
            else {"status": "ok", "error": None}
        )
        for block in READ_BLOCKS_V3
    }


def sample_contexto_plc_raw() -> dict:
    return {
        "ranges": [
            {
                "area": "H",
                "source_range": "H0-H42",
                "raw_words": [0] * 43,
            },
            {
                "area": "H",
                "source_range": "H100",
                "raw_words": [0x0000],
            },
            {
                "area": "W",
                "source_range": "W1",
                "raw_words": [0x0004],
            },
            {
                "area": "W",
                "source_range": "W4-W13",
                "raw_words": [0x0001] + [0] * 9,
            },
            {
                "area": "W",
                "source_range": "W25",
                "raw_words": [0x0000],
            },
            {
                "area": "D",
                "source_range": "D100-D116",
                "raw_words": [0, 0, 1800, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 0, 10, 0, 0],
            },
            {
                "area": "D",
                "source_range": "D500-D506",
                "raw_words": [0, 30, 8, 12, 5, 26, 2],
            },
            {
                "area": "D",
                "source_range": "D1000-D1007",
                "raw_words": [6, 0, 8, 0, 14, 0, 22, 0],
            },
            {
                "area": "D",
                "source_range": "D1008-D1009",
                "raw_words": [0, 0],
            },
            {
                "area": "D",
                "source_range": "D3630-D3651",
                "raw_words": [0] * 22,
            },
            {
                "area": "A",
                "source_range": "A351-A353",
                "raw_words": [0x3000, 0x1208, 0x2605],
            },
            {
                "area": "A",
                "source_range": "A401-A402",
                "raw_words": [0, 0],
            },
        ],
    }


def sample_payload_dict(
    failed: set[str] | None = None,
    ts: str = "2026-05-12T08:30:00+00:00",
) -> dict:
    failed = failed or set()
    salidas_raw = [0x0001] + [0] * 9
    bits = decode_vector_salidas_logicas(salidas_raw)
    secciones = [
        {
            "id": i + 1,
            "automatico_calculado": False,
            "manual_activo": False,
            "salida_interna": False,
        }
        for i in range(112)
    ]
    horarios_raw = [6, 0, 8, 0, 14, 0, 22, 0] + [0] * 20
    data = {
        "schema_version": 3,
        "ts": ts,
        "fins_ok": not failed,
        "fins_error": None if not failed else "Bloques FINS fallidos: " + "; ".join(sorted(failed)),
        "read_status": read_status(failed),
        "modo": {"modfunalu": 0, "modo_label": "horarios"},
        "fotocelula": {
            "entrada_raw": False,
            "entrada_raw_source": "W25.00",
            "mem_fun": False,
            "mem_fun_source": "H100.00",
            "filtrada_activa": False,
            "filtrada_source": "H100.01",
            "temporizador_activacion_s": 0,
            "temporizador_desactivacion_s": 0,
            "retardo_activacion_s": 10,
            "retardo_desactivacion_s": 10,
        },
        "plc_reloj": {
            "raw_words": [0, 30, 8, 12, 5, 26, 2],
            "encoding": "binary",
            "decoded": {
                "segundo": 0,
                "minuto": 30,
                "hora": 8,
                "dia": 12,
                "mes": 5,
                "anio": 26,
                "dia_semana": 2,
            },
        },
        "horarios": {"raw_words": horarios_raw, "tramos": decode_schedule_tramos(horarios_raw)},
        "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
        "reset_temporizado": {
            "w1_raw": 0x0004,
            "dm_raw_words": [1800, 0, 0, 0, 0, 0],
            "horario_global_activo": False,
            "horario_global_activo_source": "W1.01",
            "reset": {
                "activo": True,
                "activo_source": "W1.02",
                "retardo_segundo_apagado_s": 1800,
                "temporizador_segundo_apagado_s": 0,
                "contador_apagados": 0,
                "max_reintentos": 3,
            },
        },
        "hmi_original": {
            "indice_seccion": 0,
            "indice_anterior": 0,
            "automatico_seccion_seleccionada": False,
            "manual_seccion_seleccionada": False,
            "orden_transferencia_comun": False,
            "indicacion_activacion_alumbrado_seccion": False,
            "h10_raw": 0,
        },
        "reloj_ar": {
            "raw": {"A351_minsegplc": 0x3000, "A352_diahorplc": 0x1208, "A353_anomesplc": 0x2605},
            "decoded": {"minuto": 30, "segundo": 0, "dia": 12, "hora": 8, "anio": 26, "mes": 5},
            "encoding": "bcd_packed_channel",
        },
        "secciones": secciones,
        "vector_salidas_logicas": {
            "source_range": "W4-W13",
            "raw_words": salidas_raw,
            "bits": bits,
        },
        "contexto_plc_raw": sample_contexto_plc_raw(),
    }
    for block in failed:
        if block == "secciones":
            data["secciones"] = []
        elif block == "reloj":
            data["plc_reloj"] = None
        else:
            data[block] = None
    return data


def sample_payload_bytes(failed: set[str] | None = None) -> bytes:
    return json.dumps(sample_payload_dict(failed)).encode("utf-8")


def sample_variables(failed: set[str] | None = None) -> dict:
    data = sample_payload_dict(failed)
    return {
        "secciones": data["secciones"],
        "modo": data["modo"],
        "fotocelula": data["fotocelula"],
        "plc_reloj": data["plc_reloj"],
        "horarios": data["horarios"],
        "diagnostico": data["diagnostico"],
        "reset_temporizado": data["reset_temporizado"],
        "hmi_original": data["hmi_original"],
        "reloj_ar": data["reloj_ar"],
        "vector_salidas_logicas": data["vector_salidas_logicas"],
        "contexto_plc_raw": data["contexto_plc_raw"],
        "read_status": data["read_status"],
    }


def utc_dt(hour: int = 8) -> datetime:
    return datetime(2026, 5, 12, hour, 0, 0, tzinfo=timezone.utc)
