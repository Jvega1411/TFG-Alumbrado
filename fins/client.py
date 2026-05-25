import socket
from typing import Any, Dict, Optional

from config.settings import Config
from fins.frame import FINSProtocolError, build_memory_read_frame, parse_fins_response


MAX_UNMATCHED_RESPONSES = 5


class FINSClient:
    """Cliente UDP FINS de solo lectura."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config if config is not None else Config
        self.socket: Optional[socket.socket] = None
        self._sid = 0

    def connect(self) -> None:
        if self.socket is not None:
            self.close()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(self.config.UDP_TIMEOUT)
        self.socket.bind((self.config.UDP_LOCAL_HOST, self.config.UDP_LOCAL_PORT))

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _next_sid(self) -> int:
        self._sid = (self._sid % 255) + 1
        return self._sid

    def read_memory_area(self, area: str, start_address: int, word_count: int) -> Dict[str, Any]:
        if self.socket is None:
            raise RuntimeError("Cliente no conectado. Llamar connect() primero.")

        sid = self._next_sid()
        frame = build_memory_read_frame(
            area,
            start_address,
            word_count,
            self.config,
            sid=sid,
        )
        self.socket.sendto(frame, (self.config.PLC_IP, self.config.PLC_PORT))
        unmatched_sids = []
        for _ in range(MAX_UNMATCHED_RESPONSES + 1):
            response, addr = self.socket.recvfrom(4096)
            if addr[0] != self.config.PLC_IP:
                raise ValueError(f"Respuesta de IP inesperada: {addr[0]}")
            if len(response) >= 10 and response[9] != sid:
                unmatched_sids.append(response[9])
                continue
            return parse_fins_response(
                response,
                expected_sid=sid,
                expected_word_count=word_count,
                raise_on_error=True,
            )

        discarded = ", ".join(f"0x{value:02X}" for value in unmatched_sids)
        raise FINSProtocolError(
            f"No llego SID esperado 0x{sid:02X}; descartados SID: {discarded}"
        )

    def read_dm_range(self, start: int, count: int) -> Dict[str, Any]:
        return self.read_memory_area("DM", start, count)

    def read_w_range(self, start: int, count: int) -> Dict[str, Any]:
        return self.read_memory_area("WR", start, count)

    def read_h_range(self, start: int, count: int) -> Dict[str, Any]:
        return self.read_memory_area("HR", start, count)

    def read_ar_range(self, start: int, count: int) -> Dict[str, Any]:
        return self.read_memory_area("AR", start, count)

    def read_cio_range(self, start: int, count: int) -> Dict[str, Any]:
        return self.read_memory_area("CIO", start, count)
