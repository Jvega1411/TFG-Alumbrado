from subscriber.payload_schema import parse_payload
from tests.v3_helpers import sample_payload_bytes


def test_hmi_raw_index_is_zero_based_for_section_id():
    payload = parse_payload(sample_payload_bytes())
    assert payload.hmi_original.indice_seccion == 0
    selected_id = payload.hmi_original.indice_seccion + 1
    assert payload.secciones[selected_id - 1].id == selected_id
