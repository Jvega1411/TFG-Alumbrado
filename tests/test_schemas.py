from datetime import datetime, timezone

from schemas.lectura import (
    CicloResponse,
    HorarioTramoResponse,
    SeccionEstadoResponse,
    SeccionHistorialResponse,
)


def _utc_now():
    return datetime.now(tz=timezone.utc)


def test_ciclo_response_accepts_v2_fields():
    resp = CicloResponse(
        id=1,
        timestamp=_utc_now(),
        fins_ok=True,
        fins_error=None,
        secciones_status="ok",
        salidas_wr_status="ok",
        modfunalu=0,
        modo_label="horarios",
        plc_hora=8,
    )
    assert resp.modo_label == "horarios"
    assert resp.salidas_wr_status == "ok"


def test_seccion_estado_response_uses_v2_names():
    resp = SeccionEstadoResponse(
        ciclo_id=10,
        timestamp=_utc_now(),
        seccion_id=1,
        automatico_calculado=False,
        manual_activo=True,
        salida_interna=False,
        salida_wr=True,
    )
    assert resp.manual_activo is True
    assert resp.salida_wr is True


def test_horario_tramo_response_has_v2_decoded_fields():
    resp = HorarioTramoResponse(
        ciclo_id=10,
        timestamp=_utc_now(),
        tramo_id=3,
        inicio_raw=None,
        fin_raw=None,
        inicio_raw_words=None,
        fin_raw_words="[8, 0]",
        source_json='{"fin_hora":"D3632"}',
        inicio_hora=None,
        inicio_minuto=None,
        fin_hora=8,
        fin_minuto=0,
    )
    assert resp.tramo_id == 3
    assert resp.fin_hora == 8
    assert resp.fin_raw_words == [8, 0]
    assert resp.source_json == {"fin_hora": "D3632"}


def test_seccion_historial_response_inherits_section_shape():
    resp = SeccionHistorialResponse(
        ciclo_id=10,
        timestamp=_utc_now(),
        seccion_id=5,
        automatico_calculado=True,
        manual_activo=False,
        salida_interna=False,
        salida_wr=False,
    )
    assert resp.automatico_calculado is True
