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


def _parse_int_env(name: str, default: str) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        value = default
    return _parse_int(value)


class Config:
    # PLC
    PLC_IP: str = os.getenv('PLC_IP', '192.168.250.1')
    PLC_PORT: int = int(os.getenv('PLC_PORT', '9600'))
    UDP_LOCAL_HOST: str = os.getenv('UDP_LOCAL_HOST', '')
    UDP_LOCAL_PORT: int = int(os.getenv('UDP_LOCAL_PORT', '9600'))

    # FINS — soporta decimal o prefijo 0x
    FINS_SOURCE_NETWORK: int = _parse_int_env('FINS_SOURCE_NETWORK', '0')
    FINS_SOURCE_NODE: int    = _parse_int_env('FINS_SOURCE_NODE',    '0')
    FINS_SOURCE_UNIT: int    = _parse_int_env('FINS_SOURCE_UNIT',    '0')
    FINS_DEST_NETWORK: int   = _parse_int_env('FINS_DEST_NETWORK',   '0')
    FINS_DEST_NODE: int      = _parse_int_env('FINS_DEST_NODE',      '0')
    FINS_DEST_UNIT: int      = _parse_int_env('FINS_DEST_UNIT',      '0')

    UDP_TIMEOUT: float = float(os.getenv('UDP_TIMEOUT', '2.0'))

    # SQL Server
    DB_SERVER: str   = os.getenv('DB_SERVER', '')
    DB_NAME: str     = os.getenv('DB_NAME', '')
    DB_USER: str     = os.getenv('DB_USER', '')
    DB_PASSWORD: str = os.getenv('DB_PASSWORD', '')
    DB_PORT: int     = int(os.getenv('DB_PORT', '1433'))

    # Adquisición
    ACQUISITION_INTERVAL_S: float = float(os.getenv('ACQUISITION_INTERVAL_S', '10.0'))

    # Logging
    LOG_DIR: Path = _project_root / os.getenv('LOG_DIR', 'logs')

    # SQLite — Fase 1 (sobreescribir en .env para Fase 2 con SQL Server)
    DB_ESTADOS_URL: str = os.getenv(
        'DB_ESTADOS_URL',
        'sqlite:///' + str(_project_root / 'data' / 'bd_estados.db'),
    )
    DB_HIST_URL: str = os.getenv(
        'DB_HIST_URL',
        'sqlite:///' + str(_project_root / 'data' / 'bd_historizacion.db'),
    )

    # MQTT — MQTT_BROKER_HOST vacío por defecto: subred enlace no confirmada (PENDIENTE P5)
    # Configurar en .env antes de arrancar. validate_publisher() falla si está vacío.
    MQTT_BROKER_HOST: str       = os.getenv('MQTT_BROKER_HOST', '')
    MQTT_BROKER_PORT: int       = int(os.getenv('MQTT_BROKER_PORT', '1883'))
    MQTT_TOPIC: str             = os.getenv('MQTT_TOPIC', 'alumbrado/estado')
    MQTT_CLIENT_ID: str         = os.getenv('MQTT_CLIENT_ID', 'alumbrado-publisher')
    MQTT_USERNAME: str          = os.getenv('MQTT_USERNAME', '')
    MQTT_PASSWORD: str          = os.getenv('MQTT_PASSWORD', '')
    HEARTBEAT_INTERVAL_S: float = float(os.getenv('HEARTBEAT_INTERVAL_S', '30.0'))

    # FastAPI — 127.0.0.1 por defecto para no exponer en todas las interfaces sin config explícita
    API_HOST: str = os.getenv('API_HOST', '127.0.0.1')
    API_PORT: int = int(os.getenv('API_PORT', '8000'))

    # BD — False cuando el esquema V2 ya existe; true crea tablas limpias desde modelos.
    DB_AUTO_CREATE: bool = os.getenv('DB_AUTO_CREATE', 'false').lower() == 'true'

    @staticmethod
    def _parse_int(value: str) -> int:
        return _parse_int(value)

    @staticmethod
    def _parse_int_env(name: str, default: str) -> int:
        return _parse_int_env(name, default)

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
        if cls.UDP_LOCAL_HOST.strip() in {'0.0.0.0', '::'}:
            raise ValueError("UDP_LOCAL_HOST no debe abrir FINS en todas las interfaces")
        if cls.UDP_LOCAL_HOST != cls.UDP_LOCAL_HOST.strip():
            raise ValueError("UDP_LOCAL_HOST no puede tener espacios al inicio o final")
        if cls.ACQUISITION_INTERVAL_S < 2.0:
            raise ValueError(
                "ACQUISITION_INTERVAL_S no debe bajar de 2.0s contra el PLC real: "
                f"{cls.ACQUISITION_INTERVAL_S}"
            )
        if not (1 <= cls.DB_PORT <= 65535):
            raise ValueError(f"DB_PORT fuera de rango: {cls.DB_PORT}")

    @classmethod
    def _validate_db(cls) -> None:
        if not cls.DB_ESTADOS_URL.strip():
            raise ValueError("DB_ESTADOS_URL no puede estar vacia")

    @classmethod
    def _validate_mqtt(cls) -> None:
        if not cls.MQTT_BROKER_HOST.strip():
            raise ValueError("MQTT_BROKER_HOST no puede estar vacio — configurar en .env")
        if not (1 <= cls.MQTT_BROKER_PORT <= 65535):
            raise ValueError(f"MQTT_BROKER_PORT fuera de rango: {cls.MQTT_BROKER_PORT}")
        if not cls.MQTT_TOPIC.strip():
            raise ValueError("MQTT_TOPIC no puede estar vacio")
        if not cls.MQTT_CLIENT_ID.strip():
            raise ValueError("MQTT_CLIENT_ID no puede estar vacio")
        if cls.MQTT_PASSWORD and not cls.MQTT_USERNAME.strip():
            raise ValueError("MQTT_USERNAME no puede estar vacio si MQTT_PASSWORD esta configurado")
        if cls.HEARTBEAT_INTERVAL_S <= 0:
            raise ValueError(f"HEARTBEAT_INTERVAL_S debe ser positivo: {cls.HEARTBEAT_INTERVAL_S}")

    @classmethod
    def validate_api(cls) -> None:
        cls._validate_db()
        if not cls.API_HOST.strip():
            raise ValueError("API_HOST no puede estar vacio")
        if not (1 <= cls.API_PORT <= 65535):
            raise ValueError(f"API_PORT fuera de rango: {cls.API_PORT}")

    @classmethod
    def validate_mqtt(cls) -> None:
        cls._validate_mqtt()

    @classmethod
    def validate_publisher(cls) -> None:
        cls.validate()
        if not cls.UDP_LOCAL_HOST.strip():
            raise ValueError("UDP_LOCAL_HOST debe configurarse explicitamente para el publisher")
        if cls.FINS_SOURCE_NODE == 0:
            raise ValueError("FINS_SOURCE_NODE debe configurarse explicitamente para el publisher")
        if cls.FINS_DEST_NODE == 0:
            raise ValueError("FINS_DEST_NODE debe configurarse explicitamente para el publisher")
        cls._validate_mqtt()

    @classmethod
    def validate_subscriber(cls) -> None:
        cls._validate_db()
        cls._validate_mqtt()
