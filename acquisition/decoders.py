from fins.frame import parse_words_to_int_list


def words(response: dict) -> list[int]:
    """Extract FINS response data as 16-bit words."""
    return parse_words_to_int_list(response["data"])


def get_bit(word: int, bit: int) -> bool:
    if not 0 <= bit <= 15:
        raise ValueError(f"bit fuera de rango 0..15: {bit}")
    return bool((word >> bit) & 0x0001)


def extract_section_bits(raw_words: list[int], group_offset: int) -> list[bool]:
    if len(raw_words) < group_offset + 7:
        raise ValueError("faltan words para extraer 112 bits de seccion")
    result = []
    for i in range(112):
        word_idx = group_offset + i // 16
        bit_idx = i % 16
        result.append(get_bit(raw_words[word_idx], bit_idx))
    return result


def decode_u32_low_high(low: int, high: int) -> int:
    return (low & 0xFFFF) | ((high & 0xFFFF) << 16)


def decode_i32_low_high(low: int, high: int) -> int:
    value = decode_u32_low_high(low, high)
    if value & 0x80000000:
        value -= 0x100000000
    return value


def bcd_byte_to_int(byte: int) -> int:
    byte &= 0xFF
    high = (byte >> 4) & 0x0F
    low = byte & 0x0F
    if high > 9 or low > 9:
        raise ValueError(f"byte no BCD: 0x{byte:02X}")
    return high * 10 + low


def decode_modo_label(modfunalu: int) -> str:
    return {
        0: "horarios",
        1: "fotocelula",
        2: "ambos",
    }.get(modfunalu, "desconocido")


def decode_ar_clock(a351: int, a352: int, a353: int) -> dict:
    return {
        "raw": {
            "A351_minsegplc": a351,
            "A352_diahorplc": a352,
            "A353_anomesplc": a353,
        },
        "decoded": {
            "minuto": bcd_byte_to_int((a351 >> 8) & 0xFF),
            "segundo": bcd_byte_to_int(a351 & 0xFF),
            "dia": bcd_byte_to_int((a352 >> 8) & 0xFF),
            "hora": bcd_byte_to_int(a352 & 0xFF),
            "anio": bcd_byte_to_int((a353 >> 8) & 0xFF),
            "mes": bcd_byte_to_int(a353 & 0xFF),
        },
        "encoding": "bcd_packed_channel",
    }


def decode_clock_dm(raw_words: list[int], encoding: str = "binary") -> dict:
    if len(raw_words) != 7:
        raise ValueError(f"reloj DM requiere 7 words, recibido {len(raw_words)}")
    if encoding not in {"binary", "bcd"}:
        raise ValueError(f"encoding reloj no soportado: {encoding}")
    if encoding == "binary":
        values = raw_words
    else:
        values = [bcd_byte_to_int(word & 0xFF) for word in raw_words]
    return {
        "raw_words": raw_words,
        "encoding": encoding,
        "decoded": {
            "segundo": values[0],
            "minuto": values[1],
            "hora": values[2],
            "dia": values[3],
            "mes": values[4],
            "anio": values[5],
            "dia_semana": values[6],
        },
    }


def decode_schedule_tramos(raw_words: list[int]) -> list[dict]:
    if len(raw_words) != 28:
        raise ValueError(f"horarios requiere 28 words, recibido {len(raw_words)}")
    tramos = []
    # D1000..D1007: inicio/fin for tramos 1 and 2.
    base_sources = [
        ("D1000", "D1001", "D1002", "D1003"),
        ("D1004", "D1005", "D1006", "D1007"),
    ]
    for idx, sources in enumerate(base_sources):
        offset = idx * 4
        tramos.append(
            {
                "tramo": idx + 1,
                "inicio_hora": raw_words[offset],
                "inicio_minuto": raw_words[offset + 1],
                "fin_hora": raw_words[offset + 2],
                "fin_minuto": raw_words[offset + 3],
                "inicio_raw": [raw_words[offset], raw_words[offset + 1]],
                "fin_raw": [raw_words[offset + 2], raw_words[offset + 3]],
                "source": {
                    "inicio_hora": sources[0],
                    "inicio_minuto": sources[1],
                    "fin_hora": sources[2],
                    "fin_minuto": sources[3],
                },
            }
        )
    # D3632..D3651: only fin for tramos 3..12.
    for tramo in range(3, 13):
        raw_offset = 8 + (tramo - 3) * 2
        dm = 3632 + (tramo - 3) * 2
        tramos.append(
            {
                "tramo": tramo,
                "inicio_hora": None,
                "inicio_minuto": None,
                "fin_hora": raw_words[raw_offset],
                "fin_minuto": raw_words[raw_offset + 1],
                "inicio_raw": None,
                "fin_raw": [raw_words[raw_offset], raw_words[raw_offset + 1]],
                "source": {
                    "fin_hora": f"D{dm}",
                    "fin_minuto": f"D{dm + 1}",
                },
            }
        )
    return tramos


def decode_cercha_salidas(raw_words: list[int]) -> list[dict]:
    if len(raw_words) != 10:
        raise ValueError(f"salidas WR requiere 10 words, recibido {len(raw_words)}")
    salidas = []
    for idx in range(160):
        word_offset = idx // 16
        bit = idx % 16
        salidas.append(
            {
                "id": idx + 1,
                "activa": get_bit(raw_words[word_offset], bit),
                "source": f"W{4 + word_offset}.{bit:02d}",
                "physical_io_confirmed": False,
            }
        )
    return salidas
