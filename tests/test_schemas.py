from datetime import datetime, timezone

from schemas.lectura import (
    CicloResponse,
    HorarioTramoResponse,
    SeccionEstadoResponse,
    SeccionHistorialResponse,
)


def _utc_now():
    return datetime.now(tz=timezone.utc)


class TestCicloResponse:
    def test_from_dict(self):
        data = {
            "id": 1,
            "timestamp": _utc_now(),
            "fins_ok": True,
            "fins_error": None,
            "secciones_status": "ok",
            "horarios_status": "ok",
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
            "cycle_time_error": False,
            "low_battery": False,
            "io_verify_error": False,
        }
        resp = CicloResponse(**data)
        assert resp.id == 1
        assert resp.fins_ok is True
        assert resp.modfunalu == 0
        assert resp.secciones_status == "ok"

    def test_optional_fields_can_be_none(self):
        data = {
            "id": 2,
            "timestamp": _utc_now(),
            "fins_ok": False,
            "fins_error": "MRES=0x21",
            "modfunalu": None,
            "fotocelula_entrada": None,
            "fotocelula_mem_fun": None,
            "fotocelula_mem_act": None,
            "plc_seg": None,
            "plc_min": None,
            "plc_hora": None,
            "plc_dia": None,
            "plc_mes": None,
            "plc_anio": None,
            "plc_diasem": None,
            "cycle_time_error": None,
            "low_battery": None,
            "io_verify_error": None,
        }
        resp = CicloResponse(**data)
        assert resp.fins_ok is False
        assert resp.modfunalu is None


class TestSeccionEstadoResponse:
    def test_from_dict(self):
        data = {"seccion_id": 1, "automatico": True, "manual": False, "horario_activo": True}
        resp = SeccionEstadoResponse(**data)
        assert resp.seccion_id == 1
        assert resp.automatico is True

    def test_all_false(self):
        data = {"seccion_id": 112, "automatico": False, "manual": False, "horario_activo": False}
        resp = SeccionEstadoResponse(**data)
        assert resp.manual is False


class TestHorarioTramoResponse:
    def test_from_dict(self):
        data = {"tramo_id": 3, "inicio_raw": 480, "fin_raw": 1320}
        resp = HorarioTramoResponse(**data)
        assert resp.tramo_id == 3
        assert resp.inicio_raw == 480

    def test_nullable_fields(self):
        data = {"tramo_id": 1, "inicio_raw": None, "fin_raw": None}
        resp = HorarioTramoResponse(**data)
        assert resp.inicio_raw is None


class TestSeccionHistorialResponse:
    def test_from_dict(self):
        data = {
            "timestamp": _utc_now(),
            "seccion_id": 5,
            "automatico": True,
            "manual": False,
            "horario_activo": False,
        }
        resp = SeccionHistorialResponse(**data)
        assert resp.seccion_id == 5
        assert resp.automatico is True
