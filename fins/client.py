import socket
from typing import Dict, Any, Optional
from config.settings import Config
from fins.frame import build_memory_read_frame, parse_fins_response


class FINSClient:
    """Cliente UDP FINS — solo lectura."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config if config is not None else Config
        self.socket: Optional[socket.socket] = None

    def connect(self) -> None:
        if self.socket is not None:
            self.close()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(self.config.UDP_TIMEOUT)
        # Bind explícito requerido para FINS/UDP sobre Ethernet
        self.socket.bind(('', self.config.UDP_LOCAL_PORT))

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def read_memory_area(self, area: str, start_address: int, word_count: int) -> Dict[str, Any]:
        if self.socket is None:
            raise RuntimeError("Cliente no conectado. Llamar connect() primero.")
        frame = build_memory_read_frame(area, start_address, word_count, self.config)
        self.socket.sendto(frame, (self.config.PLC_IP, self.config.PLC_PORT))
        response, addr = self.socket.recvfrom(4096)
        if addr[0] != self.config.PLC_IP:
            raise ValueError(f"Respuesta de IP inesperada: {addr[0]}")
        return parse_fins_response(response)

    def read_dm_range(self, start: int, count: int) -> Dict[str, Any]:
        return self.read_memory_area('DM', start, count)

    def read_w_range(self, start: int, count: int) -> Dict[str, Any]:
        return self.read_memory_area('WR', start, count)

    def read_h_range(self, start: int, count: int) -> Dict[str, Any]:
        return self.read_memory_area('HR', start, count)
