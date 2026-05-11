import pytest

from fins.frame import (
    FINSProtocolError,
    MEMORY_AREA_CODES,
    build_memory_read_frame,
    parse_fins_response,
    parse_words_to_int_list,
)


class TestBuildMemoryReadFrame:

    def test_build_dm_read_basic(self):
        frame = build_memory_read_frame("DM", 116, 1)
        assert len(frame) == 18
        assert frame[9] == 0x00
        assert frame[10:12] == b"\x01\x01"
        assert frame[12] == 0x82
        assert frame[13:15] == b"\x00\x74"
        assert frame[15] == 0x00
        assert frame[16:18] == b"\x00\x01"

    def test_build_multiple_areas(self):
        test_cases = [
            ("DM", 0x82),
            ("WR", 0xB1),
            ("HR", 0xB2),
            ("CIO", 0xB0),
            ("AR", 0xB3),
        ]
        for area, expected_code in test_cases:
            frame = build_memory_read_frame(area, 100, 5)
            assert frame[12] == expected_code

    def test_build_large_read(self):
        frame = build_memory_read_frame("DM", 1000, 100)
        assert frame[13:15] == b"\x03\xe8"
        assert frame[16:18] == b"\x00\x64"

    def test_build_uses_sid(self):
        frame = build_memory_read_frame("DM", 116, 1, sid=7)
        assert frame[9] == 7

    def test_build_invalid_area(self):
        with pytest.raises(ValueError, match="Area .* no valida"):
            build_memory_read_frame("INVALID", 100, 1)

    def test_build_address_out_of_range(self):
        with pytest.raises(ValueError, match="start_address fuera de rango"):
            build_memory_read_frame("DM", 0x10000, 1)
        with pytest.raises(ValueError, match="start_address fuera de rango"):
            build_memory_read_frame("DM", -1, 1)

    def test_build_count_out_of_range(self):
        with pytest.raises(ValueError, match="word_count debe estar"):
            build_memory_read_frame("DM", 100, 0)
        with pytest.raises(ValueError, match="word_count debe estar"):
            build_memory_read_frame("DM", 100, 1000)

    def test_build_sid_out_of_range(self):
        with pytest.raises(ValueError, match="sid fuera de rango"):
            build_memory_read_frame("DM", 100, 1, sid=256)


class TestParseFinsResponse:

    def test_parse_success_response(self):
        response = b"\x00" * 10 + b"\x01\x01" + b"\x00\x00" + b"\x00\x0A\x00\x0B"
        result = parse_fins_response(response)
        assert result["success"] is True
        assert result["mres"] == 0x00
        assert result["sres"] == 0x00
        assert result["data"] == b"\x00\x0A\x00\x0B"
        assert result["word_count"] == 2

    def test_parse_error_response(self):
        response = b"\x00" * 10 + b"\x01\x01" + b"\x11\x00"
        result = parse_fins_response(response)
        assert result["success"] is False
        assert result["mres"] == 0x11
        assert "Command format error" in result["error_msg"]

    def test_parse_sres_nonzero_is_error(self):
        response = b"\x00" * 10 + b"\x01\x01" + b"\x00\x01"
        result = parse_fins_response(response)
        assert result["success"] is False
        assert result["mres"] == 0x00
        assert result["sres"] == 0x01

    def test_parse_response_too_short(self):
        with pytest.raises(FINSProtocolError, match="Respuesta demasiado corta"):
            parse_fins_response(b"\x00" * 13)

    def test_parse_empty_data(self):
        response = b"\x00" * 10 + b"\x01\x01" + b"\x00\x00"
        result = parse_fins_response(response)
        assert result["success"] is True
        assert result["data"] == b""
        assert result["word_count"] == 0

    def test_parse_rejects_unexpected_sid(self):
        response = b"\x00" * 9 + b"\x05" + b"\x01\x01" + b"\x00\x00"
        with pytest.raises(FINSProtocolError, match="SID inesperado"):
            parse_fins_response(response, expected_sid=6)

    def test_parse_rejects_unexpected_command_echo(self):
        response = b"\x00" * 10 + b"\x02\x01" + b"\x00\x00"
        with pytest.raises(FINSProtocolError, match="Command echo inesperado"):
            parse_fins_response(response)

    def test_parse_rejects_truncated_payload(self):
        response = b"\x00" * 10 + b"\x01\x01" + b"\x00\x00" + b"\x00\x01"
        with pytest.raises(FINSProtocolError, match="Payload truncado"):
            parse_fins_response(response, expected_word_count=2)


class TestParseWordsToIntList:

    def test_parse_single_word(self):
        assert parse_words_to_int_list(b"\x00\x05") == [5]

    def test_parse_multiple_words(self):
        assert parse_words_to_int_list(b"\x00\x01\x00\x02\x00\x03") == [1, 2, 3]

    def test_parse_large_values(self):
        assert parse_words_to_int_list(b"\xFF\xFF\x80\x00") == [65535, 32768]

    def test_parse_empty_data(self):
        assert parse_words_to_int_list(b"") == []

    def test_parse_odd_length_rejected(self):
        with pytest.raises(FINSProtocolError, match="longitud impar"):
            parse_words_to_int_list(b"\x00\x01\x00\x02\xFF")


class TestMemoryAreaCodes:

    def test_memory_area_codes_defined(self):
        for area in ["DM", "WR", "HR", "CIO", "AR"]:
            assert area in MEMORY_AREA_CODES
            assert isinstance(MEMORY_AREA_CODES[area], int)
            assert 0 <= MEMORY_AREA_CODES[area] <= 0xFF

    def test_all_codes_are_word_access(self):
        assert MEMORY_AREA_CODES["DM"] == 0x82
        assert MEMORY_AREA_CODES["WR"] == 0xB1
        assert MEMORY_AREA_CODES["HR"] == 0xB2
        assert MEMORY_AREA_CODES["CIO"] == 0xB0
        assert MEMORY_AREA_CODES["AR"] == 0xB3


@pytest.fixture
def mock_plc_response():
    def _make(data: bytes, mres: int = 0x00, sres: int = 0x00, sid: int = 0):
        return (
            b"\x80\x00\x02\x00\x00\x00\x00\x00\x00"
            + bytes([sid])
            + b"\x01\x01"
            + bytes([mres, sres])
            + data
        )
    return _make
