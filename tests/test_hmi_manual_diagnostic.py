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


def test_parser_accepts_poll_plc_local_port_override():
    diagnostic = _load_hmi_manual_diagnostic()
    args = diagnostic.build_parser().parse_args(
        ["poll-plc", "--samples", "1", "--local-port", "9601"]
    )

    assert args.local_port == 9601


def test_decode_plc_snapshot_includes_second_hmi_screen_and_context():
    diagnostic = _load_hmi_manual_diagnostic()
    h_raw = [0] * 21
    w_raw = [0] * 10
    d_raw = [0] * 17
    d_raw[16] = 2

    snapshot = diagnostic.decode_plc_snapshot(
        h10_raw=0,
        h42_raw=0xA000,
        d1008=0,
        d1009=0,
        d3630=7,
        d3631=6,
        h11_h31_raw=h_raw,
        w4_w13_raw=w_raw,
        w1_raw=0x0004,
        h100_raw=0x0002,
        w25_raw=0x0001,
        d100_d116_raw=d_raw,
    )

    assert snapshot["hmi_screen_2"]["seccion_ui"] == 8
    assert snapshot["hmi_screen_2"]["manual_seccion_seleccionada"] is True
    assert snapshot["context"]["W1"]["reset_temporizado_activo"] is True
    assert snapshot["context"]["H100"]["fotocelula_filtrada_activa"] is True
    assert snapshot["context"]["W25"]["fotocelula_entrada_raw"] is True
    assert snapshot["context"]["D100_D116"]["D116_modfunalu"] == 2


def test_format_plc_diff_reports_changed_hmi_and_sections():
    diagnostic = _load_hmi_manual_diagnostic()
    h_prev = [0] * 21
    h_curr = [0] * 21
    h_curr[7] = 0x0002
    w_prev = [0] * 10
    w_curr = [0x0002] + [0] * 9

    previous = diagnostic.decode_plc_snapshot(
        h10_raw=0,
        d1008=0,
        d1009=0,
        h11_h31_raw=h_prev,
        w4_w13_raw=w_prev,
    )
    current = diagnostic.decode_plc_snapshot(
        h10_raw=0x2000,
        d1008=1,
        d1009=0,
        h11_h31_raw=h_curr,
        w4_w13_raw=w_curr,
    )

    text = diagnostic.format_plc_diff(previous, current)

    assert "changed manual_activo: added=2 removed=-" in text
    assert "changed salida_wr: added=2 removed=-" in text
    assert "changed screen1.indice_seccion_raw: 0 -> 1" in text
    assert "changed screen1.manual_seccion_seleccionada: False -> True" in text


def test_parser_accepts_full_diff_mode():
    diagnostic = _load_hmi_manual_diagnostic()
    args = diagnostic.build_parser().parse_args(
        ["poll-plc", "--samples", "2", "--interval-seconds", "2", "--full", "--diff"]
    )

    assert args.full is True
    assert args.diff is True


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
