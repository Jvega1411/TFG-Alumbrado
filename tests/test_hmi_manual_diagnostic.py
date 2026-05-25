import importlib.util
from datetime import datetime, timezone
from pathlib import Path


def _load_hmi_manual_diagnostic():
    path = Path(__file__).parents[1] / "scripts" / "node-config" / "hmi_manual_diagnostic.py"
    spec = importlib.util.spec_from_file_location("hmi_manual_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_decode_plc_snapshot_links_hmi_index_and_section_bits():
    diagnostic = _load_hmi_manual_diagnostic()
    h_raw = [0] * 21
    h_raw[7] = 0x0001
    w_raw = [0x0001] + [0] * 9

    snapshot = diagnostic.decode_plc_snapshot(
        h10_raw=0xA000,
        d1008=0,
        d1009=1,
        h11_h31_raw=h_raw,
        w4_w13_raw=w_raw,
        timestamp_utc=datetime(2026, 5, 25, 11, 0, tzinfo=timezone.utc),
    )

    assert snapshot["hmi_original"]["seccion_ui_from_d1008"] == 1
    assert snapshot["hmi_original"]["manual_seccion_seleccionada"] is True
    assert snapshot["target_section"]["id"] == 1
    assert snapshot["target_section"]["manual_activo"] is True
    assert snapshot["target_section"]["manual_source"] == "H18.00"
    assert snapshot["target_section"]["salida_wr"] is True
    assert snapshot["target_section"]["salida_wr_source"] == "W4.00"
    assert snapshot["counts"]["manual_activo"] == 1
    assert snapshot["active_ids"]["manual_activo"] == [1]


def test_parser_rejects_sub_2s_repeated_plc_sampling():
    diagnostic = _load_hmi_manual_diagnostic()
    args = diagnostic.build_parser().parse_args(
        ["poll-plc", "--samples", "2", "--interval-seconds", "1.5"]
    )

    try:
        diagnostic.poll_plc(args)
    except SystemExit as exc:
        assert "2.0" in str(exc)
    else:
        raise AssertionError("poll_plc should reject repeated sampling below 2s")


def test_format_plc_snapshot_summarizes_target_section():
    diagnostic = _load_hmi_manual_diagnostic()
    h_raw = [0] * 21
    h_raw[14] = 0x0002
    w_raw = [0] * 10

    snapshot = diagnostic.decode_plc_snapshot(
        h10_raw=0,
        d1008=1,
        d1009=0,
        h11_h31_raw=h_raw,
        w4_w13_raw=w_raw,
    )

    text = diagnostic.format_plc_snapshot(snapshot)

    assert "target_section 2" in text
    assert "interna=ON (H25.01)" in text
