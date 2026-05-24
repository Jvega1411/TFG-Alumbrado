import pytest

from acquisition.decoders import (
    bcd_byte_to_int,
    decode_ar_clock,
    decode_cercha_salidas,
    decode_clock_dm,
    decode_i32_low_high,
    decode_modo_label,
    decode_schedule_tramos,
    decode_u32_low_high,
    extract_section_bits,
    get_bit,
    words,
)
from tests.v2_helpers import make_fins_response


def test_words_extracts_fins_data():
    assert words(make_fins_response([0x1234, 0x00FF])) == [0x1234, 0x00FF]


def test_get_bit_edges():
    assert get_bit(0x8001, 0) is True
    assert get_bit(0x8001, 15) is True
    assert get_bit(0x8001, 1) is False


def test_extract_section_bits_112_values():
    raw = [0] * 21
    raw[0] = 0x0001
    raw[6] = 0x8000
    result = extract_section_bits(raw, 0)
    assert len(result) == 112
    assert result[0] is True
    assert result[111] is True


def test_decode_32_bit_values():
    assert decode_u32_low_high(0x0001, 0x0001) == 65537
    assert decode_i32_low_high(0xFFFF, 0xFFFF) == -1


def test_bcd_validation():
    assert bcd_byte_to_int(0x59) == 59
    with pytest.raises(ValueError):
        bcd_byte_to_int(0x6A)


def test_decode_modo_label():
    assert decode_modo_label(0) == "horarios"
    assert decode_modo_label(1) == "fotocelula"
    assert decode_modo_label(2) == "ambos"
    assert decode_modo_label(99) == "desconocido"


def test_decode_ar_clock_matches_plc_text_byte_order():
    decoded = decode_ar_clock(0x3005, 0x1208, 0x2605)
    assert decoded["decoded"] == {
        "minuto": 30,
        "segundo": 5,
        "dia": 12,
        "hora": 8,
        "anio": 26,
        "mes": 5,
    }


def test_decode_clock_dm_binary():
    decoded = decode_clock_dm([5, 30, 8, 12, 5, 26, 2])
    assert decoded["decoded"]["hora"] == 8
    assert decoded["encoding"] == "binary"


def test_decode_schedule_tramos_sources_and_shape():
    raw = [6, 0, 8, 0, 14, 0, 22, 0] + list(range(20))
    tramos = decode_schedule_tramos(raw)
    assert len(tramos) == 12
    assert tramos[0]["inicio_raw"] == [6, 0]
    assert tramos[0]["source"]["fin_hora"] == "D1002"
    assert tramos[4]["inicio_raw"] is None
    assert tramos[4]["source"]["fin_hora"] == "D3636"


def test_decode_cercha_salidas_mapping():
    raw = [0] * 10
    raw[0] = 0x0001
    raw[6] = 0x8000
    raw[7] = 0x0001
    raw[9] = 0x8000
    salidas = decode_cercha_salidas(raw)
    assert len(salidas) == 160
    assert salidas[0] == {
        "id": 1,
        "activa": True,
        "source": "W4.00",
        "physical_io_confirmed": False,
    }
    assert salidas[111]["source"] == "W10.15"
    assert salidas[112]["source"] == "W11.00"
    assert salidas[159]["source"] == "W13.15"
