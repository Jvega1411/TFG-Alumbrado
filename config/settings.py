import os
from pathlib import Path
from dotenv import load_dotenv

_project_root = Path(__file__).parent.parent
load_dotenv(dotenv_path=_project_root / '.env')


def _parse_int(value: str) -> int:
    value = value.strip()
    if value.startswith(('0x', '0X')):
        return int(value, 16)
    return int(value, 10)


class Config:
    # PLC
    PLC_IP: str = os.getenv('PLC_IP', '192.168.250.1')
    PLC_PORT: int = int(os.getenv('PLC_PORT', '9600'))
    UDP_LOCAL_PORT: int = int(os.getenv('UDP_LOCAL_PORT', '9600'))

    # FINS — soporta decimal o prefijo 0x
    FINS_SOURCE_NETWORK: int = _parse_int(os.getenv('FINS_SOURCE_NETWORK', '0'))
    FINS_SOURCE_NODE: int    = _parse_int(os.getenv('FINS_SOURCE_NODE',    '0'))
    FINS_SOURCE_UNIT: int    = _parse_int(os.getenv('FINS_SOURCE_UNIT',    '0'))
    FINS_DEST_NETWORK: int   = _parse_int(os.getenv('FINS_DEST_NETWORK',   '0'))
    FINS_DEST_NODE: int      = _parse_int(os.getenv('FINS_DEST_NODE',      '0'))
    FINS_DEST_UNIT: int      = _parse_int(os.getenv('FINS_DEST_UNIT',      '0'))

    UDP_TIMEOUT: float = float(os.getenv('UDP_TIMEOUT', '2.0'))

    # SQL Server
    DB_SERVER: str   = os.getenv('DB_SERVER', '')
    DB_NAME: str     = os.getenv('DB_NAME', '')
    DB_USER: str     = os.getenv('DB_USER', '')
    DB_PASSWORD: str = os.getenv('DB_PASSWORD', '')
    DB_PORT: int     = int(os.getenv('DB_PORT', '1433'))

    # Adquisición
    ACQUISITION_INTERVAL_S: float = float(os.getenv('ACQUISITION_INTERVAL_S', '30.0'))

    # Logging
    LOG_DIR: Path = _project_root / os.getenv('LOG_DIR', 'logs')

    @staticmethod
    def _parse_int(value: str) -> int:
        return _parse_int(value)

    @classmethod
    def validate(cls) -> None:
        for attr in [
            'FINS_SOURCE_NETWORK', 'FINS_SOURCE_NODE', 'FINS_SOURCE_UNIT',
            'FINS_DEST_NETWORK',   'FINS_DEST_NODE',   'FINS_DEST_UNIT',
        ]:
            v = getattr(cls, attr)
            if not (0 <= v <= 255):
                raise ValueError(f"{attr} fuera de rango 0-255: {v}")
        if cls.UDP_TIMEOUT <= 0:
            raise ValueError(f"UDP_TIMEOUT debe ser positivo: {cls.UDP_TIMEOUT}")
        if not (1 <= cls.PLC_PORT <= 65535):
            raise ValueError(f"PLC_PORT fuera de rango: {cls.PLC_PORT}")
        if not (1 <= cls.UDP_LOCAL_PORT <= 65535):
            raise ValueError(f"UDP_LOCAL_PORT fuera de rango: {cls.UDP_LOCAL_PORT}")
        if cls.ACQUISITION_INTERVAL_S <= 0:
            raise ValueError(f"ACQUISITION_INTERVAL_S debe ser positivo: {cls.ACQUISITION_INTERVAL_S}")
        if not (1 <= cls.DB_PORT <= 65535):
            raise ValueError(f"DB_PORT fuera de rango: {cls.DB_PORT}")
