import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from config.settings import Config
from model.database import Base, create_db_engine
from model.fase2 import (
    Ciclo,
    FotocelulaState,
    HorarioTramo,
    SalidasWrState,
    SeccionEstado,
)
from subscriber.listener import process_message, run_subscriber
from tests.v2_helpers import sample_payload_bytes, sample_payload_dict


@pytest.fixture
def db_session():
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_process_message_writes_v2_cycle_and_detail_rows(db_session):
    process_message(sample_payload_bytes(), db_session)
    ciclo = db_session.query(Ciclo).one()
    assert ciclo.fins_ok is True
    assert ciclo.modfunalu == 0
    assert ciclo.modo_label == "horarios"
    assert ciclo.plc_hora == 8
    assert db_session.query(SeccionEstado).count() == 112
    assert db_session.query(HorarioTramo).count() == 12
    assert db_session.query(FotocelulaState).count() == 1
    assert db_session.query(SalidasWrState).count() == 1


def test_process_message_persists_section_v2_fields(db_session):
    process_message(sample_payload_bytes(), db_session)
    section = db_session.query(SeccionEstado).filter_by(seccion_id=1).one()
    assert section.automatico_calculado is False
    assert section.manual_activo is False
    assert section.salida_interna is False
    assert section.salida_wr is True


def test_process_message_partial_payload_keeps_ok_blocks(db_session):
    process_message(sample_payload_bytes({"diagnostico"}), db_session)
    ciclo = db_session.query(Ciclo).one()
    assert ciclo.fins_ok is False
    assert ciclo.diagnostico_status == "failed"
    assert ciclo.secciones_status == "ok"
    assert db_session.query(SeccionEstado).count() == 112


def test_process_message_failed_secciones_creates_no_section_rows(db_session):
    process_message(sample_payload_bytes({"secciones"}), db_session)
    assert db_session.query(Ciclo).count() == 1
    assert db_session.query(SeccionEstado).count() == 0


def test_invalid_payload_is_discarded(db_session):
    data = sample_payload_dict()
    data["schema_version"] = 1
    process_message(json.dumps(data).encode("utf-8"), db_session)
    assert db_session.query(Ciclo).count() == 0


def test_duplicate_timestamp_rolls_back_without_duplicate_rows(db_session):
    payload = sample_payload_bytes()
    process_message(payload, db_session)
    process_message(payload, db_session)
    assert db_session.query(Ciclo).count() == 1
    assert db_session.query(SeccionEstado).count() == 112


class TestRunSubscriber:
    def test_connects_and_subscribes(self):
        mock_client = MagicMock()

        with patch("subscriber.listener.Config.validate_subscriber"), \
             patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Config.DB_AUTO_CREATE", False), \
             patch.object(mock_client, "loop_forever", side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                run_subscriber()

        mock_client.connect.assert_called_once_with(
            Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, keepalive=60
        )
        mock_client.subscribe.assert_called_once_with(Config.MQTT_TOPIC, qos=1)

    def test_sets_mqtt_auth_when_configured(self):
        mock_client = MagicMock()

        with patch("subscriber.listener.Config.validate_subscriber"), \
             patch("subscriber.listener.Config.MQTT_USERNAME", "user"), \
             patch("subscriber.listener.Config.MQTT_PASSWORD", "secret"), \
             patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Config.DB_AUTO_CREATE", False), \
             patch.object(mock_client, "loop_forever", side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                run_subscriber()

        mock_client.username_pw_set.assert_called_once_with("user", "secret")
