import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from fins.client import FINSClient
from fins.frame import FINSError, parse_words_to_int_list
from model.estados import (
    EstadoActual,
    EstadoSistema,
    HistorialSecciones,
    HistorialSistema,
)

logger = logging.getLogger(__name__)


def extract_section_bits(words: list, group_offset: int) -> list:
    result = []
    for i in range(112):
        word_idx = group_offset + i // 16
        bit_idx = i % 16
        result.append(bool((words[word_idx] >> bit_idx) & 1))
    return result


def read_all_variables(client: FINSClient) -> dict:
    """Lee todas las variables del PLC. Lanza FINSError/OSError si falla."""
    # H11-H31: 21 words — automaticos (offset 0), manuales (offset 7), memactsec (offset 14)
    result_h = client.read_h_range(11, 21)
    words_h = parse_words_to_int_list(result_h['data'])
    automaticos = extract_section_bits(words_h, 0)
    manuales    = extract_section_bits(words_h, 7)
    memactsec   = extract_section_bits(words_h, 14)

    # D116: modfunalu
    result_d116 = client.read_dm_range(116, 1)
    modfunalu = parse_words_to_int_list(result_d116['data'])[0]

    # W25: fotocelula_entrada (bit 0)
    result_w25 = client.read_w_range(25, 1)
    w25 = parse_words_to_int_list(result_w25['data'])[0]
    fotocelula_entrada = bool(w25 & 0x0001)

    # H100: fotocelula mem (bit0 = mem_fun, bit1 = mem_act)
    result_h100 = client.read_h_range(100, 1)
    h100 = parse_words_to_int_list(result_h100['data'])[0]
    fotocelula_mem_fun = bool(h100 & 0x0001)
    fotocelula_mem_act = bool((h100 >> 1) & 0x0001)

    # D500-D506: reloj PLC (7 words)
    result_reloj = client.read_dm_range(500, 7)
    reloj = parse_words_to_int_list(result_reloj['data'])

    # D1000-D1007: horarios tramos raw (8 words)
    result_hor12 = client.read_dm_range(1000, 8)
    horarios_raw_1_2 = parse_words_to_int_list(result_hor12['data'])

    # D3632-D3651: horarios fin tramos raw (20 words)
    result_hor3_12 = client.read_dm_range(3632, 20)
    horarios_raw_3_12 = parse_words_to_int_list(result_hor3_12['data'])

    # A401: cycle_time_error (bit 8)
    result_a401 = client.read_ar_range(401, 1)
    a401 = parse_words_to_int_list(result_a401['data'])[0]
    cycle_time_error = bool((a401 >> 8) & 0x0001)

    # A402: low_battery (bit 4), io_verify_error (bit 9)
    result_a402 = client.read_ar_range(402, 1)
    a402 = parse_words_to_int_list(result_a402['data'])[0]
    low_battery     = bool((a402 >> 4) & 0x0001)
    io_verify_error = bool((a402 >> 9) & 0x0001)

    return {
        'secciones': [
            {
                'id': i + 1,
                'automatico':     automaticos[i],
                'manual':         manuales[i],
                'horario_activo': memactsec[i],
            }
            for i in range(112)
        ],
        'modfunalu':         modfunalu,
        'fotocelula_entrada': fotocelula_entrada,
        'fotocelula_mem_fun': fotocelula_mem_fun,
        'fotocelula_mem_act': fotocelula_mem_act,
        'plc_seg':    reloj[0],
        'plc_min':    reloj[1],
        'plc_hora':   reloj[2],
        'plc_dia':    reloj[3],
        'plc_mes':    reloj[4],
        'plc_anio':   reloj[5],
        'plc_diasem': reloj[6],
        'horarios_raw': horarios_raw_1_2 + horarios_raw_3_12,
        'cycle_time_error': cycle_time_error,
        'low_battery':      low_battery,
        'io_verify_error':  io_verify_error,
    }


def build_payload(ts: datetime, variables: dict) -> dict:
    return {
        'ts': ts.isoformat(),
        'fins_ok': True,
        'fins_error': None,
        'plc_reloj': {
            'seg':    variables['plc_seg'],
            'min':    variables['plc_min'],
            'hora':   variables['plc_hora'],
            'dia':    variables['plc_dia'],
            'mes':    variables['plc_mes'],
            'anio':   variables['plc_anio'],
            'diasem': variables['plc_diasem'],
        },
        'modo': {
            'modfunalu':          variables['modfunalu'],
            'fotocelula_entrada': variables['fotocelula_entrada'],
            'fotocelula_mem_fun': variables['fotocelula_mem_fun'],
            'fotocelula_mem_act': variables['fotocelula_mem_act'],
        },
        'secciones': variables['secciones'],
        'horarios': {'raw_words': variables['horarios_raw']},
        'diagnostico': {
            'cycle_time_error': variables['cycle_time_error'],
            'low_battery':      variables['low_battery'],
            'io_verify_error':  variables['io_verify_error'],
        },
    }


def build_error_payload(ts: datetime, error: str) -> dict:
    return {
        'ts': ts.isoformat(),
        'fins_ok': False,
        'fins_error': error,
    }
