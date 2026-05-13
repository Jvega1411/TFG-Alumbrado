import logging

import paho.mqtt.client as mqtt
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config.settings import Config
from model.database import Base, create_db_engine
from model.fase2 import Ciclo, HorarioTramo, SeccionEstado
from subscriber.payload_schema import parse_payload

logger = logging.getLogger(__name__)


def process_message(payload_bytes: bytes, session: Session) -> None:
    """Parse a MQTT payload and write it to DB without stopping the loop."""
    try:
        payload = parse_payload(payload_bytes)
    except (ValueError, ValidationError) as exc:
        logger.error("Payload MQTT invalido (descartado): %s", exc)
        return

    try:
        _write_to_db(payload, session)
    except SQLAlchemyError as exc:
        logger.error("Error SQLAlchemy (rollback): %s", exc)
        session.rollback()
    except Exception as exc:
        logger.error("Error inesperado en BD (rollback): %s", exc)
        session.rollback()


def _write_to_db(payload, session: Session) -> None:
    ts = payload.ts
    modo_ok = payload.block_ok("modo")
    fotocelula_ok = payload.block_ok("fotocelula")
    reloj_ok = payload.block_ok("reloj")
    diagnostico_ok = payload.block_ok("diagnostico")

    ciclo = Ciclo(
        timestamp=ts,
        fins_ok=payload.fins_ok,
        fins_error=payload.fins_error,
        secciones_status=payload.block_status("secciones"),
        secciones_error=payload.block_error("secciones"),
        modo_status=payload.block_status("modo"),
        modo_error=payload.block_error("modo"),
        fotocelula_status=payload.block_status("fotocelula"),
        fotocelula_error=payload.block_error("fotocelula"),
        reloj_status=payload.block_status("reloj"),
        reloj_error=payload.block_error("reloj"),
        horarios_status=payload.block_status("horarios"),
        horarios_error=payload.block_error("horarios"),
        diagnostico_status=payload.block_status("diagnostico"),
        diagnostico_error=payload.block_error("diagnostico"),
        modfunalu=payload.modo.modfunalu if modo_ok and payload.modo else None,
        fotocelula_entrada=payload.modo.fotocelula_entrada if fotocelula_ok and payload.modo else None,
        fotocelula_mem_fun=payload.modo.fotocelula_mem_fun if fotocelula_ok and payload.modo else None,
        fotocelula_mem_act=payload.modo.fotocelula_mem_act if fotocelula_ok and payload.modo else None,
        plc_seg=payload.plc_reloj.seg if reloj_ok and payload.plc_reloj else None,
        plc_min=payload.plc_reloj.min if reloj_ok and payload.plc_reloj else None,
        plc_hora=payload.plc_reloj.hora if reloj_ok and payload.plc_reloj else None,
        plc_dia=payload.plc_reloj.dia if reloj_ok and payload.plc_reloj else None,
        plc_mes=payload.plc_reloj.mes if reloj_ok and payload.plc_reloj else None,
        plc_anio=payload.plc_reloj.anio if reloj_ok and payload.plc_reloj else None,
        plc_diasem=payload.plc_reloj.diasem if reloj_ok and payload.plc_reloj else None,
        cycle_time_error=payload.diagnostico.cycle_time_error if diagnostico_ok and payload.diagnostico else None,
        low_battery=payload.diagnostico.low_battery if diagnostico_ok and payload.diagnostico else None,
        io_verify_error=payload.diagnostico.io_verify_error if diagnostico_ok and payload.diagnostico else None,
    )
    session.add(ciclo)
    session.flush()

    if payload.block_ok("secciones") and payload.secciones:
        for s in payload.secciones:
            session.add(
                SeccionEstado(
                    ciclo_id=ciclo.id,
                    timestamp=ts,
                    seccion_id=s.id,
                    automatico=s.automatico,
                    manual=s.manual,
                    horario_activo=s.horario_activo,
                )
            )

    # PENDIENTE P1: formato real de raw_words pendiente de smoke test FINS.
    # Provisional: 2 words por tramo, inicio=raw_words[i*2], fin=raw_words[i*2+1].
    if payload.block_ok("horarios") and payload.horarios:
        raw_words = payload.horarios.raw_words
        for i in range(12):
            session.add(
                HorarioTramo(
                    ciclo_id=ciclo.id,
                    timestamp=ts,
                    tramo_id=i + 1,
                    inicio_raw=raw_words[i * 2] if i * 2 < len(raw_words) else None,
                    fin_raw=raw_words[i * 2 + 1] if i * 2 + 1 < len(raw_words) else None,
                )
            )

    session.commit()


def run_subscriber() -> None:
    Config.validate_subscriber()

    engine = create_db_engine(Config.DB_ESTADOS_URL)
    if Config.DB_AUTO_CREATE:
        Base.metadata.create_all(engine)

    def on_message(client, userdata, message):
        with Session(engine) as session:
            process_message(message.payload, session)

    mqtt_client = mqtt.Client()
    if Config.MQTT_USERNAME.strip():
        mqtt_client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD or None)
    mqtt_client.on_message = on_message
    mqtt_client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, keepalive=60)
    mqtt_client.subscribe(Config.MQTT_TOPIC, qos=1)

    logger.info(
        "Subscriber MQTT iniciado - broker=%s:%d topic=%s",
        Config.MQTT_BROKER_HOST,
        Config.MQTT_BROKER_PORT,
        Config.MQTT_TOPIC,
    )
    mqtt_client.loop_forever()


if __name__ == "__main__":
    run_subscriber()
