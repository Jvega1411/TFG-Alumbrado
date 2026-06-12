import logging

import paho.mqtt.client as mqtt
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config.settings import Config
from model.database import Base, create_db_engine
from model.fase2 import (
    Ciclo,
    ContextoPlcRawState,
    FotocelulaState,
    HmiOriginalState,
    HorarioTramo,
    RelojArState,
    ResetTemporizadoState,
    SeccionEstado,
    VectorSalidasLogicasState,
)
from model.json_columns import dump_json_column
from schemas.blocks import READ_BLOCKS_V3
from subscriber.payload_schema import parse_payload

logger = logging.getLogger(__name__)


def process_message(payload_bytes: bytes, session: Session) -> None:
    """Parse a MQTT v3 payload and write it to DB without stopping the loop."""
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
    ciclo = _add_ciclo(payload, session)
    _add_secciones(payload, session, ciclo)
    _add_horarios(payload, session, ciclo)
    _add_fotocelula(payload, session, ciclo)
    _add_reset_temporizado(payload, session, ciclo)
    _add_hmi_original(payload, session, ciclo)
    _add_reloj_ar(payload, session, ciclo)
    _add_vector_salidas_logicas(payload, session, ciclo)
    _add_contexto_plc_raw(payload, session, ciclo)
    session.commit()


def _add_ciclo(payload, session: Session) -> Ciclo:
    ts = payload.ts
    modo = payload.modo if payload.block_ok("modo") else None
    fotocelula = payload.fotocelula if payload.block_ok("fotocelula") else None
    reloj = payload.plc_reloj if payload.block_ok("reloj") else None
    diagnostico = payload.diagnostico if payload.block_ok("diagnostico") else None

    ciclo = Ciclo(
        timestamp=ts,
        fins_ok=payload.fins_ok,
        fins_error=payload.fins_error,
        **{
            f"{block}_status": payload.block_status(block)
            for block in READ_BLOCKS_V3
        },
        **{
            f"{block}_error": payload.block_error(block)
            for block in READ_BLOCKS_V3
        },
        modfunalu=modo.modfunalu if modo else None,
        modo_label=modo.modo_label if modo else None,
        fotocelula_entrada=fotocelula.entrada_raw if fotocelula else None,
        fotocelula_mem_fun=fotocelula.mem_fun if fotocelula else None,
        fotocelula_mem_act=fotocelula.filtrada_activa if fotocelula else None,
        plc_reloj_raw_words=dump_json_column(reloj.raw_words) if reloj else None,
        plc_reloj_encoding=reloj.encoding if reloj else None,
        plc_seg=reloj.decoded.segundo if reloj else None,
        plc_min=reloj.decoded.minuto if reloj else None,
        plc_hora=reloj.decoded.hora if reloj else None,
        plc_dia=reloj.decoded.dia if reloj else None,
        plc_mes=reloj.decoded.mes if reloj else None,
        plc_anio=reloj.decoded.anio if reloj else None,
        plc_diasem=reloj.decoded.dia_semana if reloj else None,
        cycle_time_error=diagnostico.cycle_time_error if diagnostico else None,
        low_battery=diagnostico.low_battery if diagnostico else None,
        io_verify_error=diagnostico.io_verify_error if diagnostico else None,
    )
    session.add(ciclo)
    session.flush()
    return ciclo


def _add_secciones(payload, session: Session, ciclo: Ciclo) -> None:
    if payload.block_ok("secciones"):
        for section in payload.secciones:
            session.add(
                SeccionEstado(
                    ciclo_id=ciclo.id,
                    timestamp=payload.ts,
                    seccion_id=section.id,
                    automatico_calculado=section.automatico_calculado,
                    manual_activo=section.manual_activo,
                    salida_interna=section.salida_interna,
                )
            )


def _add_horarios(payload, session: Session, ciclo: Ciclo) -> None:
    if payload.block_ok("horarios"):
        for tramo in payload.horarios.tramos:
            session.add(
                HorarioTramo(
                    ciclo_id=ciclo.id,
                    timestamp=payload.ts,
                    tramo_id=tramo.tramo,
                    inicio_raw=None,
                    fin_raw=None,
                    inicio_raw_words=dump_json_column(tramo.inicio_raw),
                    fin_raw_words=dump_json_column(tramo.fin_raw),
                    source_json=dump_json_column(tramo.source),
                    inicio_hora=tramo.inicio_hora,
                    inicio_minuto=tramo.inicio_minuto,
                    fin_hora=tramo.fin_hora,
                    fin_minuto=tramo.fin_minuto,
                )
            )


def _add_fotocelula(payload, session: Session, ciclo: Ciclo) -> None:
    fotocelula = payload.fotocelula if payload.block_ok("fotocelula") else None
    if fotocelula:
        session.add(
            FotocelulaState(
                ciclo_id=ciclo.id,
                entrada_raw=fotocelula.entrada_raw,
                mem_fun=fotocelula.mem_fun,
                filtrada_activa=fotocelula.filtrada_activa,
                temporizador_activacion_s=fotocelula.temporizador_activacion_s,
                temporizador_desactivacion_s=fotocelula.temporizador_desactivacion_s,
                retardo_activacion_s=fotocelula.retardo_activacion_s,
                retardo_desactivacion_s=fotocelula.retardo_desactivacion_s,
            )
        )


def _add_reset_temporizado(payload, session: Session, ciclo: Ciclo) -> None:
    if payload.block_ok("reset_temporizado"):
        reset = payload.reset_temporizado.reset
        session.add(
            ResetTemporizadoState(
                ciclo_id=ciclo.id,
                w1_raw=payload.reset_temporizado.w1_raw,
                dm_raw_words=dump_json_column(payload.reset_temporizado.dm_raw_words),
                horario_global_activo=payload.reset_temporizado.horario_global_activo,
                reset_activo=reset.activo,
                retardo_segundo_apagado_s=reset.retardo_segundo_apagado_s,
                temporizador_segundo_apagado_s=reset.temporizador_segundo_apagado_s,
                contador_apagados=reset.contador_apagados,
                max_reintentos=reset.max_reintentos,
            )
        )


def _add_hmi_original(payload, session: Session, ciclo: Ciclo) -> None:
    if payload.block_ok("hmi_original"):
        hmi = payload.hmi_original
        session.add(
            HmiOriginalState(
                ciclo_id=ciclo.id,
                indice_seccion=hmi.indice_seccion,
                indice_anterior=hmi.indice_anterior,
                h10_raw=hmi.h10_raw,
                automatico_seccion_seleccionada=hmi.automatico_seccion_seleccionada,
                manual_seccion_seleccionada=hmi.manual_seccion_seleccionada,
                orden_transferencia_comun=hmi.orden_transferencia_comun,
                indicacion_activacion_alumbrado_seccion=hmi.indicacion_activacion_alumbrado_seccion,
            )
        )


def _add_reloj_ar(payload, session: Session, ciclo: Ciclo) -> None:
    if payload.block_ok("reloj_ar"):
        raw = payload.reloj_ar.raw
        decoded = payload.reloj_ar.decoded
        session.add(
            RelojArState(
                ciclo_id=ciclo.id,
                raw_a351=raw.A351_minsegplc,
                raw_a352=raw.A352_diahorplc,
                raw_a353=raw.A353_anomesplc,
                ar_minuto=decoded.minuto,
                ar_segundo=decoded.segundo,
                ar_dia=decoded.dia,
                ar_hora=decoded.hora,
                ar_anio=decoded.anio,
                ar_mes=decoded.mes,
                encoding=payload.reloj_ar.encoding,
            )
        )


def _add_vector_salidas_logicas(payload, session: Session, ciclo: Ciclo) -> None:
    if payload.block_ok("vector_salidas_logicas"):
        vector = payload.vector_salidas_logicas
        session.add(
            VectorSalidasLogicasState(
                ciclo_id=ciclo.id,
                source_range=vector.source_range,
                raw_words=dump_json_column(vector.raw_words),
                bits=dump_json_column([row.model_dump() for row in vector.bits]),
            )
        )


def _add_contexto_plc_raw(payload, session: Session, ciclo: Ciclo) -> None:
    if payload.block_ok("contexto_plc_raw"):
        context = payload.contexto_plc_raw
        session.add(
            ContextoPlcRawState(
                ciclo_id=ciclo.id,
                ranges=dump_json_column([row.model_dump() for row in context.ranges]),
            )
        )


def run_subscriber() -> None:
    Config.validate_subscriber()

    engine = create_db_engine(Config.DB_ESTADOS_URL)
    if Config.DB_AUTO_CREATE:
        Base.metadata.create_all(engine)

    def on_message(client, userdata, message):
        with Session(engine) as session:
            process_message(message.payload, session)

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
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
