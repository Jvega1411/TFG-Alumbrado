import logging
from datetime import datetime
from typing import Callable

from fins.client import FINSClient
from fins.frame import FINSError, parse_words_to_int_list

logger = logging.getLogger(__name__)

READ_BLOCKS = ('secciones', 'modo', 'fotocelula', 'reloj', 'horarios', 'diagnostico')


def extract_section_bits(words: list, group_offset: int) -> list:
    result = []
    for i in range(112):
        word_idx = group_offset + i // 16
        bit_idx = i % 16
        result.append(bool((words[word_idx] >> bit_idx) & 1))
    return result


def read_all_variables(client: FINSClient) -> dict:
    """Lee variables del PLC por bloques y conserva datos validos ante fallos parciales."""
    variables = _empty_variables()
    read_status = _empty_read_status()

    _read_block('secciones', read_status, lambda: _read_secciones(client), variables.update)
    _read_block('modo', read_status, lambda: _read_modo(client), variables.update)
    _read_block('fotocelula', read_status, lambda: _read_fotocelula(client), variables.update)
    _read_block('reloj', read_status, lambda: _read_reloj(client), variables.update)
    _read_block('horarios', read_status, lambda: _read_horarios(client), variables.update)
    _read_block('diagnostico', read_status, lambda: _read_diagnostico(client), variables.update)

    variables['read_status'] = read_status
    return variables


def _empty_variables() -> dict:
    return {
        'secciones': [],
        'modfunalu': None,
        'fotocelula_entrada': None,
        'fotocelula_mem_fun': None,
        'fotocelula_mem_act': None,
        'plc_seg': None,
        'plc_min': None,
        'plc_hora': None,
        'plc_dia': None,
        'plc_mes': None,
        'plc_anio': None,
        'plc_diasem': None,
        'horarios_raw': [],
        'cycle_time_error': None,
        'low_battery': None,
        'io_verify_error': None,
    }


def _empty_read_status() -> dict:
    return {block: {'status': 'absent', 'error': None} for block in READ_BLOCKS}


def _read_block(
    block: str,
    read_status: dict,
    reader: Callable[[], dict],
    apply_result: Callable[[dict], None],
) -> None:
    try:
        apply_result(reader())
        read_status[block] = {'status': 'ok', 'error': None}
    except (FINSError, OSError, ValueError, RuntimeError) as exc:
        read_status[block] = {'status': 'failed', 'error': str(exc)}
        logger.warning("Fallo lectura FINS bloque %s: %s", block, exc)


def _read_secciones(client: FINSClient) -> dict:
    result_h = client.read_h_range(11, 21)
    words_h = parse_words_to_int_list(result_h['data'])
    automaticos = extract_section_bits(words_h, 0)
    manuales = extract_section_bits(words_h, 7)
    memactsec = extract_section_bits(words_h, 14)
    return {
        'secciones': [
            {
                'id': i + 1,
                'automatico': automaticos[i],
                'manual': manuales[i],
                'horario_activo': memactsec[i],
            }
            for i in range(112)
        ],
    }


def _read_modo(client: FINSClient) -> dict:
    result_d116 = client.read_dm_range(116, 1)
    return {'modfunalu': parse_words_to_int_list(result_d116['data'])[0]}


def _read_fotocelula(client: FINSClient) -> dict:
    result_w25 = client.read_w_range(25, 1)
    w25 = parse_words_to_int_list(result_w25['data'])[0]

    result_h100 = client.read_h_range(100, 1)
    h100 = parse_words_to_int_list(result_h100['data'])[0]

    return {
        'fotocelula_entrada': bool(w25 & 0x0001),
        'fotocelula_mem_fun': bool(h100 & 0x0001),
        'fotocelula_mem_act': bool((h100 >> 1) & 0x0001),
    }


def _read_reloj(client: FINSClient) -> dict:
    result_reloj = client.read_dm_range(500, 7)
    reloj = parse_words_to_int_list(result_reloj['data'])
    return {
        'plc_seg': reloj[0],
        'plc_min': reloj[1],
        'plc_hora': reloj[2],
        'plc_dia': reloj[3],
        'plc_mes': reloj[4],
        'plc_anio': reloj[5],
        'plc_diasem': reloj[6],
    }


def _read_horarios(client: FINSClient) -> dict:
    result_hor12 = client.read_dm_range(1000, 8)
    horarios_raw_1_2 = parse_words_to_int_list(result_hor12['data'])

    result_hor3_12 = client.read_dm_range(3632, 20)
    horarios_raw_3_12 = parse_words_to_int_list(result_hor3_12['data'])

    return {'horarios_raw': horarios_raw_1_2 + horarios_raw_3_12}


def _read_diagnostico(client: FINSClient) -> dict:
    result_a401 = client.read_ar_range(401, 1)
    a401 = parse_words_to_int_list(result_a401['data'])[0]

    result_a402 = client.read_ar_range(402, 1)
    a402 = parse_words_to_int_list(result_a402['data'])[0]

    return {
        'cycle_time_error': bool((a401 >> 8) & 0x0001),
        'low_battery': bool((a402 >> 4) & 0x0001),
        'io_verify_error': bool((a402 >> 9) & 0x0001),
    }


def build_payload(ts: datetime, variables: dict) -> dict:
    read_status = variables.get('read_status', _empty_read_status())
    failed = [
        f"{block}: {status['error']}"
        for block, status in read_status.items()
        if status.get('status') != 'ok'
    ]
    modo_ok = _block_ok(read_status, 'modo')
    fotocelula_ok = _block_ok(read_status, 'fotocelula')
    return {
        'schema_version': 1,
        'ts': ts.isoformat(),
        'fins_ok': not failed,
        'fins_error': None if not failed else 'Bloques FINS fallidos: ' + '; '.join(failed),
        'read_status': read_status,
        'plc_reloj': {
            'seg': variables['plc_seg'],
            'min': variables['plc_min'],
            'hora': variables['plc_hora'],
            'dia': variables['plc_dia'],
            'mes': variables['plc_mes'],
            'anio': variables['plc_anio'],
            'diasem': variables['plc_diasem'],
        } if _block_ok(read_status, 'reloj') else None,
        'modo': {
            'modfunalu': variables['modfunalu'] if modo_ok else None,
            'fotocelula_entrada': variables['fotocelula_entrada'] if fotocelula_ok else None,
            'fotocelula_mem_fun': variables['fotocelula_mem_fun'] if fotocelula_ok else None,
            'fotocelula_mem_act': variables['fotocelula_mem_act'] if fotocelula_ok else None,
        } if modo_ok or fotocelula_ok else None,
        'secciones': variables['secciones'] if _block_ok(read_status, 'secciones') else [],
        'horarios': {'raw_words': variables['horarios_raw']} if _block_ok(read_status, 'horarios') else None,
        'diagnostico': {
            'cycle_time_error': variables['cycle_time_error'],
            'low_battery': variables['low_battery'],
            'io_verify_error': variables['io_verify_error'],
        } if _block_ok(read_status, 'diagnostico') else None,
    }


def _block_ok(read_status: dict, block: str) -> bool:
    return read_status.get(block, {}).get('status') == 'ok'


def build_error_payload(ts: datetime, error: str) -> dict:
    return {
        'schema_version': 1,
        'ts': ts.isoformat(),
        'fins_ok': False,
        'fins_error': error,
        'read_status': {
            block: {'status': 'failed', 'error': error}
            for block in READ_BLOCKS
        },
    }
