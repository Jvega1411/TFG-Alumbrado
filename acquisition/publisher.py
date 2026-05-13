import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt

from acquisition.poller import build_error_payload, build_payload, read_all_variables
from config.settings import Config
from fins.client import FINSClient
from fins.frame import FINSError

logger = logging.getLogger(__name__)


def _payloads_equal(a: dict, b: dict) -> bool:
    """Compara payloads ignorando campos que cambian por avance natural del ciclo."""
    return _without_runtime_fields(a) == _without_runtime_fields(b)


def _without_runtime_fields(payload: dict) -> dict:
    return {
        key: value
        for key, value in payload.items()
        if key not in ('ts', 'plc_reloj')
    }


def run_publisher(max_cycles: Optional[int] = None) -> None:
    """Loop principal del publisher FINS -> MQTT.

    max_cycles se usa solo en tests. En produccion queda en None para loop infinito.
    """
    Config.validate_publisher()

    mqtt_client = mqtt.Client(client_id=Config.MQTT_CLIENT_ID)
    if Config.MQTT_USERNAME.strip():
        mqtt_client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD or None)
    mqtt_client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, keepalive=60)
    mqtt_client.loop_start()

    last_payload: Optional[dict] = None
    last_publish_time = 0.0
    cycle = 0

    try:
        with FINSClient() as fins:
            while max_cycles is None or cycle < max_cycles:
                now = datetime.now(tz=timezone.utc)
                try:
                    variables = read_all_variables(fins)
                    payload = build_payload(now, variables)
                except (FINSError, OSError, ValueError) as exc:
                    payload = build_error_payload(now, str(exc))
                    logger.warning("Fallo FINS: %s", exc)

                elapsed = time.monotonic() - last_publish_time
                should_publish = (
                    last_payload is None
                    or not _payloads_equal(payload, last_payload)
                    or elapsed >= Config.HEARTBEAT_INTERVAL_S
                )

                if should_publish and _publish_payload(mqtt_client, payload):
                    last_payload = payload
                    last_publish_time = time.monotonic()

                cycle += 1
                if max_cycles is None:
                    time.sleep(Config.ACQUISITION_INTERVAL_S)
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


def _publish_payload(mqtt_client: mqtt.Client, payload: dict) -> bool:
    try:
        msg_info = mqtt_client.publish(
            Config.MQTT_TOPIC,
            json.dumps(payload),
            qos=1,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        logger.warning("MQTT publish error: %s", exc)
        return False
    try:
        msg_info.wait_for_publish(timeout=5.0)
    except (ValueError, RuntimeError, OSError) as exc:
        logger.warning("MQTT wait_for_publish error: %s", exc)
        return False

    published = msg_info.rc == mqtt.MQTT_ERR_SUCCESS and msg_info.is_published()
    if published:
        logger.info("MQTT publicado - fins_ok=%s", payload['fins_ok'])
    else:
        logger.warning(
            "MQTT publish no confirmado: rc=%s is_published=%s",
            msg_info.rc,
            msg_info.is_published(),
        )
    return published


if __name__ == '__main__':
    run_publisher()
