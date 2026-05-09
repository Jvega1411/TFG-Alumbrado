import binascii


def hexdump(b: bytes, maxlen: int = 256) -> str:
    if not b:
        return "<empty>"
    return binascii.hexlify(b[:maxlen]).decode("ascii")


def decode_endcode(endcode_bytes: bytes) -> int:
    """Decodifica los 2 bytes de endcode FINS a entero. Retorna 0xFFFF si malformado."""
    if len(endcode_bytes) != 2:
        return 0xFFFF
    return (endcode_bytes[0] << 8) | endcode_bytes[1]


def endcode_ok(endcode_bytes: bytes) -> bool:
    return decode_endcode(endcode_bytes) == 0x0000
