import json

import pytest

from subscriber.payload_schema import parse_payload
from tests.v3_helpers import sample_payload_bytes, sample_payload_dict


def test_accepts_valid_v3_payload():
    payload = parse_payload(sample_payload_bytes())
    assert payload.schema_version == 3
    assert payload.fins_ok is True
    assert payload.block_ok("vector_salidas_logicas") is True
    assert payload.block_ok("contexto_plc_raw") is True
    assert len(payload.secciones) == 112
    assert len(payload.vector_salidas_logicas.bits) == 160
    assert set(payload.contexto_plc_raw.ranges[0].model_dump()) == {
        "area",
        "source_range",
        "raw_words",
    }
    assert [row.source_range for row in payload.contexto_plc_raw.ranges] == [
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


def test_rejects_schema_v2_payload():
    data = sample_payload_dict()
    data["schema_version"] = 2
    with pytest.raises(ValueError):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_missing_read_status_block():
    data = sample_payload_dict()
    del data["read_status"]["vector_salidas_logicas"]
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


def test_rejects_salida_wr_in_secciones():
    data = sample_payload_dict()
    data["secciones"][0]["salida_wr"] = True
    with pytest.raises(ValueError, match="salida_wr"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_allows_secciones_ok_when_vector_salidas_logicas_failed():
    payload = parse_payload(sample_payload_bytes({"vector_salidas_logicas"}))
    assert payload.block_ok("secciones") is True
    assert payload.block_ok("vector_salidas_logicas") is False
    assert payload.vector_salidas_logicas is None


def test_rejects_bad_fixed_lengths():
    data = sample_payload_dict()
    data["vector_salidas_logicas"]["raw_words"].append(0)
    with pytest.raises(ValueError):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_context_raw_bad_length():
    data = sample_payload_dict()
    data["contexto_plc_raw"]["ranges"][0]["raw_words"] = [0] * 42
    with pytest.raises(ValueError, match="H0-H42"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_context_raw_semantic_metadata():
    data = sample_payload_dict()
    data["contexto_plc_raw"]["warnings"] = ["does_not_confirm_physical_light_state"]
    with pytest.raises(ValueError, match="warnings"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_context_raw_range_purpose():
    data = sample_payload_dict()
    data["contexto_plc_raw"]["ranges"][0]["purpose"] = "not_plc_raw"
    with pytest.raises(ValueError, match="purpose"):
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


def test_rejects_vector_bit_source_mismatch():
    data = sample_payload_dict()
    data["vector_salidas_logicas"]["bits"][0]["source"] = "W4.01"
    with pytest.raises(ValueError, match="source"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_vector_physical_io_confirmed_field():
    data = sample_payload_dict()
    data["vector_salidas_logicas"]["bits"][0]["physical_io_confirmed"] = True
    with pytest.raises(ValueError, match="physical_io_confirmed"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_vector_mapping_status_fields():
    data = sample_payload_dict()
    data["vector_salidas_logicas"]["mapping_status"] = "logical_output_vector_not_section_index"
    with pytest.raises(ValueError, match="mapping_status"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_vector_bit_active_mismatch_with_raw_words():
    data = sample_payload_dict()
    data["vector_salidas_logicas"]["raw_words"][0] = 0
    with pytest.raises(ValueError, match="raw_words"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_vector_bit_inactive_mismatch_with_raw_words():
    data = sample_payload_dict()
    data["vector_salidas_logicas"]["bits"][1]["activa"] = False
    data["vector_salidas_logicas"]["raw_words"][0] = 0x0003
    with pytest.raises(ValueError, match="raw_words"):
        parse_payload(json.dumps(data).encode("utf-8"))


def test_rejects_invalid_utf8_and_json():
    with pytest.raises(ValueError):
        parse_payload(b"\xff\xfe")
    with pytest.raises(ValueError):
        parse_payload(b"not-json")
