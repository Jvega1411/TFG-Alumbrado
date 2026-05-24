import json

import pytest

from subscriber.payload_schema import parse_payload
from tests.v2_helpers import sample_payload_bytes, sample_payload_dict


def test_accepts_valid_v2_payload():
    payload = parse_payload(sample_payload_bytes())
    assert payload.schema_version == 2
    assert payload.fins_ok is True
    assert payload.block_ok("salidas_wr") is True
    assert len(payload.secciones) == 112
    assert len(payload.salidas_wr.cercha_salidas) == 160


def test_rejects_schema_v1_payload():
    data = sample_payload_dict()
    data["schema_version"] = 1
    with pytest.raises(ValueError):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_missing_read_status_block():
    data = sample_payload_dict()
    del data["read_status"]["salidas_wr"]
    with pytest.raises(ValueError, match="read_status"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_fins_ok_incoherent_with_block_failure():
    data = sample_payload_dict({"reloj"})
    data["fins_ok"] = True
    data["fins_error"] = None
    with pytest.raises(ValueError, match="fins_ok"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_failed_block_with_payload_data():
    data = sample_payload_dict({"fotocelula"})
    data["fotocelula"] = sample_payload_dict()["fotocelula"]
    with pytest.raises(ValueError, match="fotocelula"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_sections_without_112_ids():
    data = sample_payload_dict()
    data["secciones"] = data["secciones"][:-1]
    with pytest.raises(ValueError, match="1..112"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_salidas_wr_mirror_mismatch():
    data = sample_payload_dict()
    data["secciones"][0]["salida_wr"] = False
    with pytest.raises(ValueError, match="salida_wr"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_allows_secciones_ok_when_salidas_wr_failed_with_none_mirror():
    payload = parse_payload(sample_payload_bytes({"salidas_wr"}))
    assert payload.block_ok("secciones") is True
    assert payload.block_ok("salidas_wr") is False
    assert all(section.salida_wr is None for section in payload.secciones)


def test_rejects_bad_fixed_lengths():
    data = sample_payload_dict()
    data["salidas_wr"]["raw_words"].append(0)
    with pytest.raises(ValueError):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_naive_timestamp():
    data = sample_payload_dict()
    data["ts"] = "2026-05-12T08:30:00"
    with pytest.raises(ValueError, match="timezone"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_hmi_index_out_of_range():
    data = sample_payload_dict()
    data["hmi_original"]["indice_seccion"] = 112
    with pytest.raises(ValueError):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_modo_label_mismatch():
    data = sample_payload_dict()
    data["modo"]["modfunalu"] = 2
    data["modo"]["modo_label"] = "fotocelula"
    with pytest.raises(ValueError, match="modo_label"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_clock_raw_decoded_mismatch():
    data = sample_payload_dict()
    data["plc_reloj"]["decoded"]["segundo"] = 59
    with pytest.raises(ValueError, match="reloj"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_cercha_source_mismatch():
    data = sample_payload_dict()
    data["salidas_wr"]["cercha_salidas"][0]["source"] = "W4.01"
    with pytest.raises(ValueError, match="source"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_invalid_utf8_and_json():
    with pytest.raises(ValueError):
        parse_payload(b"\xff\xfe")
    with pytest.raises(ValueError):
        parse_payload(b"not-json")
