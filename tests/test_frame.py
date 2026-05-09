import pytest
from fins.frame import (
    build_memory_read_frame,
    parse_fins_response,
    parse_words_to_int_list,
    MEMORY_AREA_CODES,
)


class TestBuildMemoryReadFrame:

    def test_build_dm_read_basic(self):
        frame = build_memory_read_frame('DM', 116, 1)
        # Header(10) + Command(2) + Payload(6) = 18 bytes
        assert len(frame) == 18
        assert frame[9] == 0x00              # SID
        assert frame[10:12] == b'\x01\x01'   # Memory Area Read
        assert frame[12] == 0x82             # DM
        assert frame[13:15] == b'\x00\x74'   # dirección 116
        assert frame[15] == 0x00             # bit position = 0 (word access)
        assert frame[16:18] == b'\x00\x01'   # count = 1

    def test_build_multiple_areas(self):
        test_cases = [
            ('DM',  0x82),
            ('WR',  0xB1),  # word access — confirmado contra PLC real
            ('HR',  0xB2),  # word access — confirmado contra PLC real
            ('CIO', 0x30),  # PENDIENTE verificar en rack
            ('AR',  0x33),  # PENDIENTE verificar en rack
        ]
        for area, expected_code in test_cases:
            frame = build_memory_read_frame(area, 100, 5)
            assert frame[12] == expected_code, f"Área {area}: código incorrecto"

    def test_build_large_read(self):
        frame = build_memory_read_frame('DM', 1000, 100)
        assert frame[13:15] == b'\x03\xe8'   # 1000 = 0x03E8
        assert frame[16:18] == b'\x00\x64'   # 100 = 0x0064

    def test_build_invalid_area(self):
        with pytest.raises(ValueError, match="Área .* no válida"):
            build_memory_read_frame('INVALID', 100, 1)

    def test_build_address_out_of_range(self):
        with pytest.raises(ValueError, match="start_address fuera de rango"):
            build_memory_read_frame('DM', 0x10000, 1)
        with pytest.raises(ValueError, match="start_address fuera de rango"):
            build_memory_read_frame('DM', -1, 1)

    def test_build_count_out_of_range(self):
        with pytest.raises(ValueError, match="word_count debe estar"):
            build_memory_read_frame('DM', 100, 0)
        with pytest.raises(ValueError, match="word_count debe estar"):
            build_memory_read_frame('DM', 100, 1000)


class TestParseFinsResponse:

    def test_parse_success_response(self):
        header = b'\x00' * 10
        response = header + b'\x01\x01' + b'\x00\x00' + b'\x00\x0A\x00\x0B'
        result = parse_fins_response(response)
        assert result['success'] is True
        assert result['mres'] == 0x00
        assert result['sres'] == 0x00
        assert result['data'] == b'\x00\x0A\x00\x0B'
        assert result['word_count'] == 2

    def test_parse_error_response(self):
        header = b'\x00' * 10
        response = header + b'\x01\x01' + b'\x11\x00'
        result = parse_fins_response(response)
        assert result['success'] is False
        assert result['mres'] == 0x11
        assert 'Command format error' in result['error_msg']

    def test_parse_response_too_short(self):
        with pytest.raises(ValueError, match="Respuesta demasiado corta"):
            parse_fins_response(b'\x00' * 13)

    def test_parse_empty_data(self):
        header = b'\x00' * 10
        response = header + b'\x01\x01' + b'\x00\x00'
        result = parse_fins_response(response)
        assert result['success'] is True
        assert result['data'] == b''
        assert result['word_count'] == 0


class TestParseWordsToIntList:

    def test_parse_single_word(self):
        assert parse_words_to_int_list(b'\x00\x05') == [5]

    def test_parse_multiple_words(self):
        assert parse_words_to_int_list(b'\x00\x01\x00\x02\x00\x03') == [1, 2, 3]

    def test_parse_large_values(self):
        assert parse_words_to_int_list(b'\xFF\xFF\x80\x00') == [65535, 32768]

    def test_parse_empty_data(self):
        assert parse_words_to_int_list(b'') == []

    def test_parse_odd_length(self):
        # byte suelto al final se descarta
        assert parse_words_to_int_list(b'\x00\x01\x00\x02\xFF') == [1, 2]


class TestMemoryAreaCodes:

    def test_memory_area_codes_defined(self):
        for area in ['DM', 'WR', 'HR', 'CIO', 'AR']:
            assert area in MEMORY_AREA_CODES
            assert isinstance(MEMORY_AREA_CODES[area], int)
            assert 0 <= MEMORY_AREA_CODES[area] <= 0xFF

    def test_wr_hr_are_word_access_codes(self):
        # Validar que WR y HR usan códigos de word access, no bit access.
        # Confirmado contra PLC real (ROV3.py + CSV outputs 2026-03-05).
        assert MEMORY_AREA_CODES['WR'] == 0xB1
        assert MEMORY_AREA_CODES['HR'] == 0xB2
        assert MEMORY_AREA_CODES['DM'] == 0x82


@pytest.fixture
def mock_plc_response():
    def _make(data: bytes, mres: int = 0x00, sres: int = 0x00):
        return b'\x80\x00\x02\x00\x00\x00\x00\x00\x00\x00' + b'\x01\x01' + bytes([mres, sres]) + data
    return _make
