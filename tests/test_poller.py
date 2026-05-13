from datetime import datetime, timezone
from unittest.mock import Mock

from acquisition.poller import (
    build_error_payload,
    build_payload,
    extract_section_bits,
    read_all_variables,
)


def _make_words_bytes(words: list) -> bytes:
    result = b''
    for w in words:
        result += bytes([(w >> 8) & 0xFF, w & 0xFF])
    return result


def _make_fins_response(words: list) -> dict:
    data = _make_words_bytes(words)
    return {'success': True, 'mres': 0, 'sres': 0, 'data': data, 'word_count': len(words)}


class TestExtractSectionBits:

    def test_all_zeros_returns_false_for_all(self):
        words = [0] * 21
        result = extract_section_bits(words, 0)
        assert len(result) == 112
        assert all(v is False for v in result)

    def test_all_ones_returns_true_for_all(self):
        words = [0xFFFF] * 21
        result = extract_section_bits(words, 0)
        assert all(v is True for v in result)

    def test_section1_is_bit0_of_first_word(self):
        words = [0] * 21
        words[0] = 0x0001
        result = extract_section_bits(words, 0)
        assert result[0] is True
        assert result[1] is False

    def test_section16_is_bit15_of_first_word(self):
        words = [0] * 21
        words[0] = 0x8000
        result = extract_section_bits(words, 0)
        assert result[14] is False
        assert result[15] is True

    def test_section17_is_bit0_of_second_word(self):
        words = [0] * 21
        words[1] = 0x0001
        result = extract_section_bits(words, 0)
        assert result[15] is False
        assert result[16] is True

    def test_section112_is_bit15_of_seventh_word(self):
        words = [0] * 21
        words[6] = 0x8000
        result = extract_section_bits(words, 0)
        assert result[110] is False
        assert result[111] is True

    def test_group_offset_selects_correct_group(self):
        words = [0] * 21
        words[7] = 0x0001
        result_group0 = extract_section_bits(words, 0)
        result_group7 = extract_section_bits(words, 7)
        assert result_group0[0] is False
        assert result_group7[0] is True

    def test_returns_exactly_112_values(self):
        assert len(extract_section_bits([0] * 21, 0)) == 112
        assert len(extract_section_bits([0] * 21, 7)) == 112
        assert len(extract_section_bits([0] * 21, 14)) == 112


class TestReadAllVariables:

    def _make_client(self):
        client = Mock()
        client.read_h_range.return_value = _make_fins_response([0] * 21)
        client.read_dm_range.side_effect = lambda start, count: _make_fins_response([0] * count)
        client.read_w_range.return_value = _make_fins_response([0])
        client.read_ar_range.return_value = _make_fins_response([0])
        return client

    def test_returns_112_secciones(self):
        result = read_all_variables(self._make_client())
        assert len(result['secciones']) == 112

    def test_seccion_ids_are_1_to_112(self):
        result = read_all_variables(self._make_client())
        ids = [s['id'] for s in result['secciones']]
        assert ids == list(range(1, 113))

    def test_all_zeros_returns_false_states(self):
        result = read_all_variables(self._make_client())
        for s in result['secciones']:
            assert s['automatico'] is False
            assert s['manual'] is False
            assert s['horario_activo'] is False

    def test_h11_bit0_sets_seccion1_automatico(self):
        client = self._make_client()
        words_h = [0] * 21
        words_h[0] = 0x0001  # H11 bit0 → seccion 1 automatico
        client.read_h_range.return_value = _make_fins_response(words_h)
        result = read_all_variables(client)
        assert result['secciones'][0]['automatico'] is True
        assert result['secciones'][0]['manual'] is False

    def test_h18_bit0_sets_seccion1_manual(self):
        client = self._make_client()
        words_h = [0] * 21
        words_h[7] = 0x0001  # H18 bit0 → seccion 1 manual (group_offset=7)
        client.read_h_range.return_value = _make_fins_response(words_h)
        result = read_all_variables(client)
        assert result['secciones'][0]['manual'] is True

    def test_d116_modfunalu(self):
        client = self._make_client()
        client.read_dm_range.side_effect = lambda start, count: (
            _make_fins_response([2]) if start == 116
            else _make_fins_response([0] * count)
        )
        result = read_all_variables(client)
        assert result['modfunalu'] == 2

    def test_w25_bit0_fotocelula_entrada(self):
        client = self._make_client()
        client.read_w_range.return_value = _make_fins_response([0x0001])
        result = read_all_variables(client)
        assert result['fotocelula_entrada'] is True

    def test_h100_bit0_fotocelula_mem_fun(self):
        client = self._make_client()
        def h_range_side_effect(start, count):
            if start == 100:
                return _make_fins_response([0x0001])  # bit0=1
            return _make_fins_response([0] * count)
        client.read_h_range.side_effect = h_range_side_effect
        result = read_all_variables(client)
        assert result['fotocelula_mem_fun'] is True
        assert result['fotocelula_mem_act'] is False

    def test_a401_bit8_cycle_time_error(self):
        client = self._make_client()
        def ar_side_effect(start, count):
            if start == 401:
                return _make_fins_response([0x0100])  # bit8 = 1
            return _make_fins_response([0])
        client.read_ar_range.side_effect = ar_side_effect
        result = read_all_variables(client)
        assert result['cycle_time_error'] is True

    def test_a402_bit4_low_battery(self):
        client = self._make_client()
        def ar_side_effect(start, count):
            if start == 402:
                return _make_fins_response([0x0010])  # bit4 = 1
            return _make_fins_response([0])
        client.read_ar_range.side_effect = ar_side_effect
        result = read_all_variables(client)
        assert result['low_battery'] is True

    def test_a402_bit9_io_verify_error(self):
        client = self._make_client()
        def ar_side_effect(start, count):
            if start == 402:
                return _make_fins_response([0x0200])  # bit9 = 1
            return _make_fins_response([0])
        client.read_ar_range.side_effect = ar_side_effect
        result = read_all_variables(client)
        assert result['io_verify_error'] is True

    def test_reloj_plc_parsed(self):
        client = self._make_client()
        reloj = [5, 30, 8, 12, 5, 2026, 2]
        client.read_dm_range.side_effect = lambda start, count: (
            _make_fins_response(reloj) if start == 500
            else _make_fins_response([0] * count)
        )
        result = read_all_variables(client)
        assert result['plc_seg'] == 5
        assert result['plc_min'] == 30
        assert result['plc_hora'] == 8
        assert result['plc_anio'] == 2026


def _sample_variables() -> dict:
    return {
        'secciones': [{'id': i+1, 'automatico': False, 'manual': False, 'horario_activo': False} for i in range(112)],
        'modfunalu': 0,
        'fotocelula_entrada': False,
        'fotocelula_mem_fun': False,
        'fotocelula_mem_act': False,
        'plc_seg': 0, 'plc_min': 30, 'plc_hora': 8,
        'plc_dia': 12, 'plc_mes': 5, 'plc_anio': 2026, 'plc_diasem': 2,
        'horarios_raw': [0] * 28,
        'cycle_time_error': False,
        'low_battery': False,
        'io_verify_error': False,
    }


class TestBuildPayload:

    def test_fins_ok_true(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_payload(ts, _sample_variables())
        assert payload['fins_ok'] is True
        assert payload['fins_error'] is None

    def test_ts_is_iso_string(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_payload(ts, _sample_variables())
        assert isinstance(payload['ts'], str)
        assert '2026' in payload['ts']

    def test_has_112_secciones(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_payload(ts, _sample_variables())
        assert len(payload['secciones']) == 112

    def test_modfunalu_in_modo(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        vars_ = _sample_variables()
        vars_['modfunalu'] = 1
        payload = build_payload(ts, vars_)
        assert payload['modo']['modfunalu'] == 1

    def test_reloj_plc_hora(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        vars_ = _sample_variables()
        vars_['plc_hora'] = 14
        payload = build_payload(ts, vars_)
        assert payload['plc_reloj']['hora'] == 14

    def test_horarios_raw_words_length(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_payload(ts, _sample_variables())
        assert len(payload['horarios']['raw_words']) == 28

    def test_diagnostico_fields(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        vars_ = _sample_variables()
        vars_['low_battery'] = True
        payload = build_payload(ts, vars_)
        assert payload['diagnostico']['low_battery'] is True
        assert payload['diagnostico']['cycle_time_error'] is False


class TestBuildErrorPayload:

    def test_fins_ok_false(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_error_payload(ts, 'MRES=0x21 SRES=0x08')
        assert payload['fins_ok'] is False
        assert payload['fins_error'] == 'MRES=0x21 SRES=0x08'

    def test_has_ts(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_error_payload(ts, 'timeout')
        assert 'ts' in payload

    def test_no_secciones_key(self):
        ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
        payload = build_error_payload(ts, 'timeout')
        assert 'secciones' not in payload
