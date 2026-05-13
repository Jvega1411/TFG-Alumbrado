import json

import pytest

from subscriber.payload_schema import parse_payload


def _valid_bytes(fins_ok: bool = True) -> bytes:
    secciones = [
        {"id": i + 1, "automatico": False, "manual": False, "horario_activo": False}
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
        data = {"ts": "2026-05-12T08:30:00+00:00", "fins_ok": False, "fins_error": "timeout"}
    return json.dumps(data).encode("utf-8")


class TestParsePayload:
    def test_valid_fins_ok_payload_parses(self):
        payload = parse_payload(_valid_bytes(fins_ok=True))
        assert payload.fins_ok is True
        assert len(payload.secciones) == 112

    def test_valid_fins_error_payload_parses(self):
        payload = parse_payload(_valid_bytes(fins_ok=False))
        assert payload.fins_ok is False
        assert payload.fins_error == "timeout"
        assert payload.secciones == []

    def test_partial_payload_with_secciones_ok_parses(self):
        secciones = [
            {"id": i + 1, "automatico": False, "manual": False, "horario_activo": False}
            for i in range(112)
        ]
        data = {
            "schema_version": 1,
            "ts": "2026-05-12T08:30:00+00:00",
            "fins_ok": False,
            "fins_error": "diagnostico: timeout",
            "read_status": {
                "secciones": {"status": "ok", "error": None},
                "diagnostico": {"status": "failed", "error": "timeout"},
            },
            "secciones": secciones,
            "diagnostico": None,
        }
        payload = parse_payload(json.dumps(data).encode("utf-8"))
        assert payload.fins_ok is False
        assert payload.block_ok("secciones") is True
        assert len(payload.secciones) == 112

    def test_missing_ts_raises(self):
        data = json.dumps({"fins_ok": True}).encode("utf-8")
        with pytest.raises(ValueError, match="ts"):
            parse_payload(data)

    def test_invalid_json_raises_valueerror(self):
        with pytest.raises(ValueError, match="JSON"):
            parse_payload(b"not valid json {{{")

    def test_invalid_utf8_raises_valueerror(self):
        with pytest.raises(ValueError, match="UTF"):
            parse_payload(b"\xff\xfe invalid bytes")

    def test_wrong_seccion_count_raises(self):
        secciones = [
            {"id": i + 1, "automatico": False, "manual": False, "horario_activo": False}
            for i in range(111)
        ]
        data = _full_payload(secciones=secciones)
        with pytest.raises(ValueError, match="112"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_duplicate_seccion_id_raises(self):
        secciones = [
            {"id": 1, "automatico": False, "manual": False, "horario_activo": False}
            for _ in range(112)
        ]
        data = _full_payload(secciones=secciones)
        with pytest.raises(ValueError, match="duplicados"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_extra_field_rejected(self):
        data = _full_payload()
        data["campo_extra_inesperado"] = "valor"
        with pytest.raises(ValueError):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_string_coercion_rejected_for_bool(self):
        data = _full_payload()
        data["fins_ok"] = "true"
        with pytest.raises(ValueError):
            parse_payload(json.dumps(data).encode("utf-8"))


def _full_payload(secciones=None):
    if secciones is None:
        secciones = [
            {"id": i + 1, "automatico": False, "manual": False, "horario_activo": False}
            for i in range(112)
        ]
    return {
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
