import json
import logging
import sys
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from config.settings import Config

logger = logging.getLogger(__name__)


def _format_payload(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def run_json_listener() -> None:
    """Subscribe to the configured MQTT topic and print received JSON payloads."""
    Config.validate_mqtt()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    def on_connect(client, userdata, flags, reason_code, properties):
        if getattr(reason_code, "is_failure", False) or (
            isinstance(reason_code, int) and reason_code != 0
        ):
            logger.error("Conexion MQTT fallida: %s", reason_code)
            return
        client.subscribe(Config.MQTT_TOPIC, qos=1)
        logger.info(
            "JSON listener iniciado - broker=%s:%d topic=%s",
            Config.MQTT_BROKER_HOST,
            Config.MQTT_BROKER_PORT,
            Config.MQTT_TOPIC,
        )

    def on_message(client, userdata, message):
        ts = datetime.now(timezone.utc).isoformat()
        print(f"\n===== MQTT {ts} topic={message.topic} bytes={len(message.payload)} =====")
        print(_format_payload(message.payload))
        sys.stdout.flush()

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if Config.MQTT_USERNAME.strip():
        mqtt_client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD or None)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, keepalive=60)
    mqtt_client.loop_forever()


if __name__ == "__main__":
    run_json_listener()
