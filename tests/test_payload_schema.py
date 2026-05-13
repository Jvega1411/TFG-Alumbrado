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
                "modo": {"status": "failed", "error": "skipped"},
                "fotocelula": {"status": "failed", "error": "skipped"},
                "reloj": {"status": "failed", "error": "skipped"},
                "horarios": {"status": "failed", "error": "skipped"},
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

    def test_reloj_ok_requires_plc_reloj(self):
        data = _full_payload()
        data["read_status"] = _read_status_with("reloj", "ok")
        data["plc_reloj"] = None
        with pytest.raises(ValueError, match="reloj"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_modo_ok_requires_modfunalu(self):
        data = _full_payload()
        data["read_status"] = _read_status_with("modo", "ok")
        data["modo"]["modfunalu"] = None
        with pytest.raises(ValueError, match="modo"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_fotocelula_ok_requires_fotocelula_fields(self):
        data = _full_payload()
        data["read_status"] = _read_status_with("fotocelula", "ok")
        data["modo"]["fotocelula_entrada"] = None
        with pytest.raises(ValueError, match="fotocelula"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_diagnostico_ok_requires_diagnostico(self):
        data = _full_payload()
        data["read_status"] = _read_status_with("diagnostico", "ok")
        data["diagnostico"] = None
        with pytest.raises(ValueError, match="diagnostico"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_horarios_ok_requires_24_raw_words(self):
        data = _full_payload()
        data["read_status"] = _read_status_with("horarios", "ok")
        data["horarios"] = {"raw_words": [0] * 23}
        with pytest.raises(ValueError, match="24"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_read_status_requires_exact_blocks(self):
        data = _full_payload()
        data["read_status"] = _read_status_with("secciones", "ok")
        del data["read_status"]["diagnostico"]
        with pytest.raises(ValueError, match="exactamente"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_fins_ok_must_match_read_status(self):
        data = _full_payload()
        data["schema_version"] = 1
        data["fins_ok"] = False
        data["read_status"] = _read_status_with("secciones", "ok")
        with pytest.raises(ValueError, match="fins_ok"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_failed_secciones_rejects_present_rows(self):
        data = _full_payload()
        data["schema_version"] = 1
        data["fins_ok"] = False
        data["read_status"] = _read_status_with("secciones", "failed")
        data["secciones"] = [
            {"id": i + 1, "automatico": False, "manual": False, "horario_activo": False}
            for i in range(112)
        ]
        with pytest.raises(ValueError, match="secciones"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_failed_reloj_rejects_present_plc_reloj(self):
        data = _full_payload()
        data["schema_version"] = 1
        data["fins_ok"] = False
        data["read_status"] = _read_status_with("reloj", "failed")
        with pytest.raises(ValueError, match="reloj"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_failed_horarios_rejects_empty_horarios_object(self):
        data = _full_payload()
        data["schema_version"] = 1
        data["fins_ok"] = False
        data["read_status"] = _read_status_with("horarios", "failed")
        data["horarios"] = {"raw_words": []}
        with pytest.raises(ValueError, match="horarios"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_modo_can_keep_modfunalu_when_fotocelula_failed(self):
        data = _full_payload()
        data["fins_ok"] = False
        data["read_status"] = _read_status_with("modo", "ok")
        data["read_status"]["fotocelula"] = {"status": "failed", "error": "timeout"}
        data["modo"]["fotocelula_entrada"] = None
        data["modo"]["fotocelula_mem_fun"] = None
        data["modo"]["fotocelula_mem_act"] = None
        payload = parse_payload(json.dumps(data).encode("utf-8"))
        assert payload.block_ok("modo") is True
        assert payload.block_ok("fotocelula") is False

    def test_fotocelula_can_keep_fields_when_modo_failed(self):
        data = _full_payload()
        data["fins_ok"] = False
        data["read_status"] = _read_status_with("fotocelula", "ok")
        data["read_status"]["modo"] = {"status": "failed", "error": "timeout"}
        data["modo"]["modfunalu"] = None
        payload = parse_payload(json.dumps(data).encode("utf-8"))
        assert payload.block_ok("modo") is False
        assert payload.block_ok("fotocelula") is True
        assert payload.modo.fotocelula_entrada is False

    def test_modo_failed_rejects_modfunalu(self):
        data = _full_payload()
        data["fins_ok"] = False
        data["read_status"] = _read_status_with("fotocelula", "ok")
        data["read_status"]["modo"] = {"status": "failed", "error": "timeout"}
        with pytest.raises(ValueError, match="modo"):
            parse_payload(json.dumps(data).encode("utf-8"))

    def test_fotocelula_failed_rejects_fotocelula_fields(self):
        data = _full_payload()
        data["fins_ok"] = False
        data["read_status"] = _read_status_with("modo", "ok")
        data["read_status"]["fotocelula"] = {"status": "failed", "error": "timeout"}
        with pytest.raises(ValueError, match="fotocelula"):
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


def _read_status_with(ok_block: str, status: str) -> dict:
    blocks = ["secciones", "modo", "fotocelula", "reloj", "horarios", "diagnostico"]
    read_status = {block: {"status": "ok", "error": None} for block in blocks}
    read_status[ok_block] = {"status": status, "error": None if status == "ok" else status}
    return read_status
