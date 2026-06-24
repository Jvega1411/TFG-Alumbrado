"""Helpers for collecting chapter 9 validation evidence.

The commands in this module are read-only. They avoid printing secrets and only
emit sanitized configuration, a single validated MQTT payload, or a consistent
SQLite backup.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Config
from schemas.blocks import READ_BLOCKS_V3
from subscriber.payload_schema import parse_payload


def _sqlite_path_from_url(url: str) -> Path | None:
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite"):
        return None
    if not parsed.database or parsed.database == ":memory:":
        return None
    path = Path(parsed.database)
    return path if path.is_absolute() else PROJECT_ROOT / path


def safe_db_logical(url: str) -> str:
    """Return a credential-free DB locator suitable for evidence manifests."""
    try:
        parsed = make_url(url)
    except Exception:
        return "<configured database>"

    if parsed.drivername.startswith("sqlite"):
        if parsed.database == ":memory:":
            return "sqlite:///:memory:"
        db_path = _sqlite_path_from_url(url)
        return f"sqlite:///{db_path}" if db_path is not None else "sqlite:///<configured>"

    host = parsed.host or "<host>"
    port = f":{parsed.port}" if parsed.port else ""
    database = f"/{parsed.database}" if parsed.database else ""
    return f"{parsed.drivername}://{host}{port}{database}"


def api_base_url(host: str, port: int) -> str:
    url_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    if ":" in url_host and not url_host.startswith("["):
        url_host = f"[{url_host}]"
    return f"http://{url_host}:{port}"


def config_snapshot() -> dict[str, Any]:
    Config.validate_api()
    Config.validate_mqtt()
    return {
        "api_host": Config.API_HOST,
        "api_port": Config.API_PORT,
        "api_base": api_base_url(Config.API_HOST, Config.API_PORT),
        "mqtt_topic": Config.MQTT_TOPIC,
        "acquisition_interval_s": Config.ACQUISITION_INTERVAL_S,
        "heartbeat_interval_s": Config.HEARTBEAT_INTERVAL_S,
        "db_logical": safe_db_logical(Config.DB_ESTADOS_URL),
    }


def payload_counts(data: dict[str, Any]) -> dict[str, Any]:
    vector = data.get("vector_salidas_logicas") or {}
    context = data.get("contexto_plc_raw") or {}
    return {
        "schema_version": data.get("schema_version"),
        "read_status_blocks": list((data.get("read_status") or {}).keys()),
        "secciones": len(data.get("secciones") or []),
        "vector_raw_words": len(vector.get("raw_words") or []),
        "vector_bits": len(vector.get("bits") or []),
        "context_raw_ranges": len(context.get("ranges") or []),
    }


def cmd_config_json(_args: argparse.Namespace) -> int:
    print(json.dumps(config_snapshot(), indent=2, sort_keys=True))
    return 0


def cmd_payload_summary(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(json.dumps(payload_counts(data), indent=2, sort_keys=True))
    return 0


def cmd_sqlite_backup(args: argparse.Namespace) -> int:
    Config._validate_db()
    source = _sqlite_path_from_url(Config.DB_ESTADOS_URL)
    if source is None:
        raise SystemExit("DB_ESTADOS_URL no es SQLite; snapshot consistente no disponible")
    if not source.exists():
        raise SystemExit(f"SQLite no existe: {source}")

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(destination)) as dst:
        src.backup(dst)

    print(f"sqlite_backup={destination}")
    return 0


def cmd_mqtt_once(args: argparse.Namespace) -> int:
    Config.validate_mqtt()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    received = threading.Event()
    errors: list[str] = []
    payload_data: dict[str, Any] | None = None

    def on_connect(client, _userdata, _flags, reason_code, _properties):
        if getattr(reason_code, "is_failure", False) or (
            isinstance(reason_code, int) and reason_code != 0
        ):
            errors.append(f"Conexion MQTT fallida: {reason_code}")
            received.set()
            return
        client.subscribe(Config.MQTT_TOPIC, qos=1)

    def on_message(client, _userdata, message):
        nonlocal payload_data
        try:
            parsed = parse_payload(message.payload)
            data = json.loads(message.payload.decode("utf-8"))
            if set(data.get("read_status", {})) != set(READ_BLOCKS_V3):
                raise ValueError("read_status no contiene exactamente los once bloques V3")
            parsed.model_dump()
            payload_data = data
        except Exception as exc:  # noqa: BLE001 - surface validation failure verbatim
            errors.append(f"payload MQTT invalido: {exc}")
        finally:
            received.set()
            client.disconnect()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if Config.MQTT_USERNAME.strip():
        client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD or None)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, keepalive=60)
        client.loop_start()
        if not received.wait(args.timeout_seconds):
            errors.append(
                f"timeout esperando mensaje MQTT en topic {Config.MQTT_TOPIC} "
                f"({args.timeout_seconds}s)"
            )
    finally:
        client.loop_stop()
        client.disconnect()

    if errors:
        raise SystemExit("; ".join(errors))
    if payload_data is None:
        raise SystemExit("no se recibio payload MQTT")

    output.write_text(
        json.dumps(payload_data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(payload_counts(payload_data), indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capitulo 9 evidence helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("config-json").set_defaults(func=cmd_config_json)

    mqtt_parser = subparsers.add_parser("mqtt-once")
    mqtt_parser.add_argument("--output", required=True)
    mqtt_parser.add_argument("--timeout-seconds", type=int, default=120)
    mqtt_parser.set_defaults(func=cmd_mqtt_once)

    backup_parser = subparsers.add_parser("sqlite-backup")
    backup_parser.add_argument("--output", required=True)
    backup_parser.set_defaults(func=cmd_sqlite_backup)

    summary_parser = subparsers.add_parser("payload-summary")
    summary_parser.add_argument("--input", required=True)
    summary_parser.set_defaults(func=cmd_payload_summary)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
