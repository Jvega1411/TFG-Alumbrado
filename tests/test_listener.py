import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from acquisition.poller import build_payload
from model.database import Base, create_db_engine
from model.fase2 import Ciclo, HorarioTramo, SeccionEstado
from subscriber.listener import process_message, run_subscriber


@pytest.fixture
def db_session():
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _valid_payload(fins_ok: bool = True, seccion1_auto: bool = False) -> bytes:
    secciones = [
        {"id": i + 1, "automatico": i == 0 and seccion1_auto, "manual": False, "horario_activo": False}
        for i in range(112)
    ]
    if fins_ok:
        data = {
            "ts": "2026-05-12T08:30:00+00:00",
            "fins_ok": True,
            "fins_error": None,
            "plc_reloj": {"seg": 0, "min": 30, "hora": 8, "dia": 12, "mes": 5, "anio": 2026, "diasem": 2},
            "modo": {
                "modfunalu": 0,
                "fotocelula_entrada": False,
                "fotocelula_mem_fun": False,
                "fotocelula_mem_act": False,
            },
            "secciones": secciones,
            "horarios": {"raw_words": [0] * 28},
            "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
        }
    else:
        data = {
            "ts": "2026-05-12T08:30:00+00:00",
            "fins_ok": False,
            "fins_error": "MRES=0x21 SRES=0x08",
        }
    return json.dumps(data).encode("utf-8")


def _partial_payload(secciones_ok: bool = True, horarios_ok: bool = True) -> bytes:
    secciones = [
        {"id": i + 1, "automatico": i == 0, "manual": False, "horario_activo": False}
        for i in range(112)
    ]
    data = {
        "schema_version": 1,
        "ts": "2026-05-12T08:30:00+00:00",
        "fins_ok": False,
        "fins_error": "diagnostico: timeout",
        "read_status": {
            "secciones": {"status": "ok" if secciones_ok else "failed", "error": None if secciones_ok else "timeout"},
            "modo": {"status": "ok", "error": None},
            "fotocelula": {"status": "ok", "error": None},
            "reloj": {"status": "ok", "error": None},
            "horarios": {"status": "ok" if horarios_ok else "failed", "error": None if horarios_ok else "timeout"},
            "diagnostico": {"status": "failed", "error": "timeout"},
        },
        "plc_reloj": {"seg": 0, "min": 30, "hora": 8, "dia": 12, "mes": 5, "anio": 2026, "diasem": 2},
        "modo": {"modfunalu": 0, "fotocelula_entrada": False, "fotocelula_mem_fun": False, "fotocelula_mem_act": False},
        "secciones": secciones if secciones_ok else [],
        "horarios": {"raw_words": [0] * 28} if horarios_ok else None,
        "diagnostico": None,
    }
    return json.dumps(data).encode("utf-8")


class TestProcessMessageValidPayload:
    def test_creates_ciclo_row(self, db_session):
        process_message(_valid_payload(), db_session)
        assert db_session.query(Ciclo).count() == 1

    def test_ciclo_fins_ok_true(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.fins_ok is True

    def test_ciclo_timestamp_is_aware(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.timestamp.tzinfo is not None

    def test_creates_112_seccion_rows(self, db_session):
        process_message(_valid_payload(), db_session)
        assert db_session.query(SeccionEstado).count() == 112

    def test_seccion_ids_are_1_to_112(self, db_session):
        process_message(_valid_payload(), db_session)
        ids = [s.seccion_id for s in db_session.query(SeccionEstado).order_by(SeccionEstado.seccion_id).all()]
        assert ids == list(range(1, 113))

    def test_seccion1_automatico_false_by_default(self, db_session):
        process_message(_valid_payload(seccion1_auto=False), db_session)
        sec1 = db_session.query(SeccionEstado).filter(SeccionEstado.seccion_id == 1).first()
        assert sec1.automatico is False

    def test_seccion1_automatico_true(self, db_session):
        process_message(_valid_payload(seccion1_auto=True), db_session)
        sec1 = db_session.query(SeccionEstado).filter(SeccionEstado.seccion_id == 1).first()
        assert sec1.automatico is True

    def test_creates_12_horario_tramo_rows(self, db_session):
        process_message(_valid_payload(), db_session)
        assert db_session.query(HorarioTramo).count() == 12

    def test_horario_tramo_timestamp_equals_ciclo_timestamp(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        tramo = db_session.query(HorarioTramo).first()
        assert tramo.timestamp == ciclo.timestamp

    def test_horario_tramo_ids_are_1_to_12(self, db_session):
        process_message(_valid_payload(), db_session)
        ids = [h.tramo_id for h in db_session.query(HorarioTramo).order_by(HorarioTramo.tramo_id).all()]
        assert ids == list(range(1, 13))

    def test_ciclo_modfunalu(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.modfunalu == 0

    def test_ciclo_reloj_hora(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.plc_hora == 8
        assert ciclo.plc_anio == 2026

    def test_seccion_timestamp_equals_ciclo_timestamp(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        sec = db_session.query(SeccionEstado).first()
        assert sec.timestamp == ciclo.timestamp

    def test_seccion_ciclo_id_matches(self, db_session):
        process_message(_valid_payload(), db_session)
        ciclo = db_session.query(Ciclo).first()
        sec = db_session.query(SeccionEstado).first()
        assert sec.ciclo_id == ciclo.id


class TestProcessMessageErrorPayload:
    def test_fins_error_creates_ciclo(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        assert db_session.query(Ciclo).count() == 1

    def test_fins_error_ciclo_fins_ok_false(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.fins_ok is False

    def test_fins_error_stores_error_message(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert "MRES" in ciclo.fins_error

    def test_fins_error_no_seccion_rows(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        assert db_session.query(SeccionEstado).count() == 0

    def test_fins_error_no_horario_rows(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        assert db_session.query(HorarioTramo).count() == 0

    def test_fins_error_modfunalu_is_none(self, db_session):
        process_message(_valid_payload(fins_ok=False), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.modfunalu is None


class TestProcessMessagePartialPayload:
    def test_partial_with_secciones_ok_creates_seccion_rows(self, db_session):
        process_message(_partial_payload(secciones_ok=True, horarios_ok=False), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.fins_ok is False
        assert ciclo.secciones_status == "ok"
        assert ciclo.diagnostico_status == "failed"
        assert db_session.query(SeccionEstado).count() == 112

    def test_partial_with_horarios_ok_creates_horario_rows(self, db_session):
        process_message(_partial_payload(secciones_ok=False, horarios_ok=True), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.horarios_status == "ok"
        assert db_session.query(HorarioTramo).count() == 12

    def test_partial_with_secciones_failed_creates_no_seccion_rows(self, db_session):
        process_message(_partial_payload(secciones_ok=False, horarios_ok=True), db_session)
        assert db_session.query(SeccionEstado).count() == 0

    def test_poller_payload_with_reloj_failed_keeps_secciones(self, db_session):
        payload = _poller_payload_with_failed_block("reloj")
        process_message(json.dumps(payload).encode("utf-8"), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.reloj_status == "failed"
        assert ciclo.plc_hora is None
        assert db_session.query(SeccionEstado).count() == 112

    def test_poller_payload_with_modo_failed_keeps_fotocelula(self, db_session):
        payload = _poller_payload_with_failed_block("modo")
        process_message(json.dumps(payload).encode("utf-8"), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.modo_status == "failed"
        assert ciclo.modfunalu is None
        assert ciclo.fotocelula_status == "ok"
        assert ciclo.fotocelula_entrada is False

    def test_poller_payload_with_fotocelula_failed_keeps_modo(self, db_session):
        payload = _poller_payload_with_failed_block("fotocelula")
        process_message(json.dumps(payload).encode("utf-8"), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.modo_status == "ok"
        assert ciclo.modfunalu == 0
        assert ciclo.fotocelula_status == "failed"
        assert ciclo.fotocelula_entrada is None

    def test_poller_payload_with_diagnostico_failed_keeps_secciones(self, db_session):
        payload = _poller_payload_with_failed_block("diagnostico")
        process_message(json.dumps(payload).encode("utf-8"), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.diagnostico_status == "failed"
        assert ciclo.cycle_time_error is None
        assert db_session.query(SeccionEstado).count() == 112

    def test_poller_payload_with_horarios_failed_creates_no_horario_rows(self, db_session):
        payload = _poller_payload_with_failed_block("horarios")
        process_message(json.dumps(payload).encode("utf-8"), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.horarios_status == "failed"
        assert db_session.query(HorarioTramo).count() == 0

    def test_poller_payload_with_secciones_failed_creates_no_seccion_rows(self, db_session):
        payload = _poller_payload_with_failed_block("secciones")
        process_message(json.dumps(payload).encode("utf-8"), db_session)
        ciclo = db_session.query(Ciclo).first()
        assert ciclo.secciones_status == "failed"
        assert db_session.query(SeccionEstado).count() == 0

    def test_duplicate_payload_does_not_duplicate_rows(self, db_session):
        payload = _valid_payload()
        process_message(payload, db_session)
        process_message(payload, db_session)
        assert db_session.query(Ciclo).count() == 1
        assert db_session.query(SeccionEstado).count() == 112
        assert db_session.query(HorarioTramo).count() == 12


class TestProcessMessageMalformedPayload:
    def test_invalid_json_creates_nothing(self, db_session):
        process_message(b"not valid json {{{", db_session)
        assert db_session.query(Ciclo).count() == 0

    def test_invalid_utf8_creates_nothing(self, db_session):
        process_message(b"\xff\xfe invalid", db_session)
        assert db_session.query(Ciclo).count() == 0

    def test_missing_ts_creates_nothing(self, db_session):
        payload = json.dumps({"fins_ok": True}).encode("utf-8")
        process_message(payload, db_session)
        assert db_session.query(Ciclo).count() == 0

    def test_invalid_ts_creates_nothing(self, db_session):
        payload = json.dumps({"ts": "not-a-date", "fins_ok": True}).encode("utf-8")
        process_message(payload, db_session)
        assert db_session.query(Ciclo).count() == 0

    def test_incomplete_secciones_creates_nothing(self, db_session):
        secciones = [
            {"id": i + 1, "automatico": False, "manual": False, "horario_activo": False}
            for i in range(111)
        ]
        data = {
            "ts": "2026-05-12T08:30:00+00:00",
            "fins_ok": True,
            "fins_error": None,
            "plc_reloj": {"seg": 0, "min": 0, "hora": 0, "dia": 1, "mes": 1, "anio": 2026, "diasem": 1},
            "modo": {
                "modfunalu": 0,
                "fotocelula_entrada": False,
                "fotocelula_mem_fun": False,
                "fotocelula_mem_act": False,
            },
            "secciones": secciones,
            "horarios": {"raw_words": [0] * 28},
            "diagnostico": {"cycle_time_error": False, "low_battery": False, "io_verify_error": False},
        }
        process_message(json.dumps(data).encode("utf-8"), db_session)
        assert db_session.query(Ciclo).count() == 0

    def test_short_horarios_creates_nothing(self, db_session):
        data = json.loads(_valid_payload().decode("utf-8"))
        data["horarios"] = {"raw_words": [0] * 23}
        process_message(json.dumps(data).encode("utf-8"), db_session)
        assert db_session.query(Ciclo).count() == 0


def _poller_payload_with_failed_block(block: str) -> dict:
    variables = _sample_variables_for_poller()
    variables["read_status"][block] = {"status": "failed", "error": f"timeout {block}"}
    if block == "secciones":
        variables["secciones"] = []
    elif block == "modo":
        variables["modfunalu"] = None
    elif block == "fotocelula":
        variables["fotocelula_entrada"] = None
        variables["fotocelula_mem_fun"] = None
        variables["fotocelula_mem_act"] = None
    elif block == "reloj":
        for key in ["plc_seg", "plc_min", "plc_hora", "plc_dia", "plc_mes", "plc_anio", "plc_diasem"]:
            variables[key] = None
    elif block == "horarios":
        variables["horarios_raw"] = []
    elif block == "diagnostico":
        variables["cycle_time_error"] = None
        variables["low_battery"] = None
        variables["io_verify_error"] = None
    ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
    return build_payload(ts, variables)


def _sample_variables_for_poller() -> dict:
    return {
        "secciones": [
            {"id": i + 1, "automatico": False, "manual": False, "horario_activo": False}
            for i in range(112)
        ],
        "modfunalu": 0,
        "fotocelula_entrada": False,
        "fotocelula_mem_fun": False,
        "fotocelula_mem_act": False,
        "plc_seg": 0,
        "plc_min": 30,
        "plc_hora": 8,
        "plc_dia": 12,
        "plc_mes": 5,
        "plc_anio": 2026,
        "plc_diasem": 2,
        "horarios_raw": [0] * 28,
        "cycle_time_error": False,
        "low_battery": False,
        "io_verify_error": False,
        "read_status": {
            "secciones": {"status": "ok", "error": None},
            "modo": {"status": "ok", "error": None},
            "fotocelula": {"status": "ok", "error": None},
            "reloj": {"status": "ok", "error": None},
            "horarios": {"status": "ok", "error": None},
            "diagnostico": {"status": "ok", "error": None},
        },
    }


class TestRunSubscriber:
    def test_connects_to_configured_broker(self):
        mock_client = MagicMock()

        with patch("subscriber.listener.Config.validate_subscriber"), \
             patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Config.DB_AUTO_CREATE", False), \
             patch.object(mock_client, "loop_forever", side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                run_subscriber()

        from config.settings import Config

        mock_client.connect.assert_called_once_with(
            Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, keepalive=60
        )

    def test_subscribes_to_configured_topic(self):
        mock_client = MagicMock()

        with patch("subscriber.listener.Config.validate_subscriber"), \
             patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Config.DB_AUTO_CREATE", False), \
             patch.object(mock_client, "loop_forever", side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                run_subscriber()

        from config.settings import Config

        mock_client.subscribe.assert_called_once_with(Config.MQTT_TOPIC, qos=1)

    def test_calls_loop_forever(self):
        mock_client = MagicMock()
        loop_called = [False]

        def fake_loop():
            loop_called[0] = True
            raise KeyboardInterrupt

        mock_client.loop_forever = fake_loop

        with patch("subscriber.listener.Config.validate_subscriber"), \
             patch("subscriber.listener.mqtt.Client", return_value=mock_client), \
             patch("subscriber.listener.create_db_engine"), \
             patch("subscriber.listener.Config.DB_AUTO_CREATE", False):
            with pytest.raises(KeyboardInterrupt):
                run_subscriber()

        assert loop_called[0] is True

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
