from datetime import datetime, timezone
from unittest.mock import Mock

from acquisition.poller import build_error_payload, build_payload, read_all_variables
from schemas.blocks import READ_BLOCKS_V3
from subscriber.payload_schema import parse_payload
from tests.v3_helpers import make_fins_response, sample_variables


def _make_client():
    client = Mock()

    def h_range(start, count):
        if start == 0:
            raw = [0] * 43
            raw[10] = 0x2000
            raw[18] = 0x0001
            return make_fins_response(raw)
        if start == 10:
            return make_fins_response([0x2000])
        if start == 11:
            raw = [0] * 21
            raw[7] = 0x0001
            return make_fins_response(raw)
        if start == 100:
            return make_fins_response([0x0002])
        return make_fins_response([0] * count)

    def w_range(start, count):
        if start == 1:
            return make_fins_response([0x0004])
        if start == 4:
            return make_fins_response([0x0001] + [0] * 9)
        if start == 25:
            return make_fins_response([0x0001])
        return make_fins_response([0] * count)

    def dm_range(start, count):
        values = {
            100: [0, 0, 1800, 0, 0, 0, 1, 0, 0, 0, 0, 0, 10, 0, 10, 0, 2],
            102: [1800, 0, 0, 0, 1, 0],
            108: [0, 0, 0, 0, 10, 0, 10, 0],
            116: [2],
            500: [5, 30, 8, 12, 5, 26, 2],
            1000: [6, 0, 8, 0, 14, 0, 22, 0],
            1008: [0, 0],
            3630: [0] * 22,
            3632: [0] * 20,
        }
        return make_fins_response(values.get(start, [0] * count))

    def ar_range(start, count):
        if start == 351:
            return make_fins_response([0x3005, 0x1208, 0x2605])
        if start == 401:
            return make_fins_response([0, 0])
        if start == 402:
            return make_fins_response([0])
        return make_fins_response([0] * count)

    client.read_h_range.side_effect = h_range
    client.read_w_range.side_effect = w_range
    client.read_dm_range.side_effect = dm_range
    client.read_ar_range.side_effect = ar_range
    return client


def test_read_all_variables_reads_v3_blocks_and_raw_context():
    result = read_all_variables(_make_client())
    assert tuple(result["read_status"]) == READ_BLOCKS_V3
    assert all(status["status"] == "ok" for status in result["read_status"].values())
    assert len(result["secciones"]) == 112
    assert result["secciones"][0]["manual_activo"] is True
    assert "salida_wr" not in result["secciones"][0]
    assert result["vector_salidas_logicas"]["bits"][0]["activa"] is True
    assert tuple(result["contexto_plc_raw"]) == ("ranges",)
    assert result["contexto_plc_raw"]["ranges"][0]["source_range"] == "H0-H42"
    assert result["contexto_plc_raw"]["ranges"][0]["raw_words"][10] == 0x2000
    assert result["contexto_plc_raw"]["ranges"][0]["raw_words"][18] == 0x0001
    assert "purpose" not in result["contexto_plc_raw"]["ranges"][0]
    assert result["modo"]["modo_label"] == "ambos"
    assert result["fotocelula"]["entrada_raw"] is True
    assert result["plc_reloj"]["decoded"]["hora"] == 8
    assert result["reloj_ar"]["decoded"]["segundo"] == 5


def test_read_all_variables_keeps_partial_data_on_block_failure():
    client = _make_client()

    def fail_reloj(start, count):
        if start == 500:
            raise RuntimeError("timeout reloj")
        return _make_client().read_dm_range(start, count)

    client.read_dm_range.side_effect = fail_reloj
    result = read_all_variables(client)
    assert result["read_status"]["reloj"]["status"] == "failed"
    assert result["plc_reloj"] is None
    assert result["read_status"]["secciones"]["status"] == "ok"
    assert len(result["secciones"]) == 112


def test_build_payload_is_valid_v3():
    ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
    payload = build_payload(ts, sample_variables())
    parsed = parse_payload(__import__("json").dumps(payload).encode("utf-8"))
    assert parsed.schema_version == 3
    assert parsed.fins_ok is True
    assert parsed.block_ok("vector_salidas_logicas") is True
    assert parsed.block_ok("contexto_plc_raw") is True


def test_real_poller_output_builds_valid_v3_payload():
    ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
    variables = read_all_variables(_make_client())
    payload = build_payload(ts, variables)
    parsed = parse_payload(__import__("json").dumps(payload).encode("utf-8"))
    ranges = parsed.contexto_plc_raw.ranges
    assert [row.source_range for row in ranges] == [
        "H0-H42",
        "H100",
        "W1",
        "W4-W13",
        "W25",
        "D100-D116",
        "D500-D506",
        "D1000-D1007",
        "D1008-D1009",
        "D3630-D3651",
        "A351-A353",
        "A401-A402",
    ]
    assert [len(row.raw_words) for row in ranges] == [43, 1, 1, 10, 1, 17, 7, 8, 2, 22, 3, 2]


def test_build_payload_failed_block_sets_payload_none():
    ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
    payload = build_payload(ts, sample_variables({"reloj"}))
    assert payload["fins_ok"] is False
    assert payload["plc_reloj"] is None
    assert payload["read_status"]["reloj"]["status"] == "failed"
    parse_payload(__import__("json").dumps(payload).encode("utf-8"))


def test_build_error_payload_marks_all_blocks_failed():
    ts = datetime(2026, 5, 12, 8, 30, 0, tzinfo=timezone.utc)
    payload = build_error_payload(ts, "timeout")
    assert payload["schema_version"] == 3
    assert payload["fins_ok"] is False
    assert set(payload["read_status"]) == set(READ_BLOCKS_V3)
    assert all(status["status"] == "failed" for status in payload["read_status"].values())
    parse_payload(__import__("json").dumps(payload).encode("utf-8"))
