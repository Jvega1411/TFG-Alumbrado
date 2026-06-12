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
    assert "salida_wr" not in snapshot["target_section"]
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
    assert "changed screen1.indice_seccion_raw: 0 -> 1" in text
    assert "changed screen1.manual_seccion_seleccionada: False -> True" in text


def test_format_word_change_reports_bit_delta():
    diagnostic = _load_hmi_manual_diagnostic()

    text = diagnostic.format_word_change("H18", 0x0000, 0x0003)

    assert text == "H18: 0 -> 3 (0x0000 -> 0x0003) bits added=0-1 removed=-"


def test_format_wide_diff_reports_only_changed_words():
    diagnostic = _load_hmi_manual_diagnostic()

    text = diagnostic.format_wide_diff(
        {"H18": 0, "D116": 1},
        {"H18": 1, "D116": 1},
        limit=10,
    )

    assert "H18: 0 -> 1" in text
    assert "D116" not in text


def test_filter_known_volatiles_keeps_hmi_and_output_candidates():
    diagnostic = _load_hmi_manual_diagnostic()

    filtered = diagnostic.filter_known_volatiles(
        {"A351": 1, "D500": 2, "W0": 3, "H18": 4, "W4": 5, "CIO1070": 6}
    )

    assert filtered == {"H18": 4, "W4": 5, "CIO1070": 6}


def test_decode_ascii_words_decodes_high_low_bytes_until_nul():
    diagnostic = _load_hmi_manual_diagnostic()

    text = diagnostic.decode_ascii_words(
        [0x414D, 0x204E, 0x3120, 0x4C31, 0x4C32, 0x0000]
    )

    assert text == "AM N1 L1L2"


def test_format_wide_status_reports_liveness_without_changes():
    diagnostic = _load_hmi_manual_diagnostic()

    text = diagnostic.format_wide_status({"W4": 0, "W5": 2}, limit=10)

    assert "status: 2 words leidos, 1 words no cero" in text
    assert "W5=0x0002" in text


def test_parser_accepts_wide_plc_mode():
    diagnostic = _load_hmi_manual_diagnostic()
    args = diagnostic.build_parser().parse_args(
        [
            "wide-plc",
            "--samples",
            "2",
            "--interval-seconds",
            "5",
            "--local-port",
            "9600",
            "--limit",
            "20",
            "--status-every",
            "3",
        ]
    )

    assert args.samples == 2
    assert args.interval_seconds == 5
    assert args.local_port == 9600
    assert args.limit == 20
    assert args.status_every == 3
    assert args.profile == "standard"
    assert args.show_known_volatile is False


def test_parser_accepts_exhaustive_wide_plc_profile():
    diagnostic = _load_hmi_manual_diagnostic()
    args = diagnostic.build_parser().parse_args(
        [
            "wide-plc",
            "--samples",
            "2",
            "--interval-seconds",
            "5",
            "--profile",
            "exhaustive",
        ]
    )

    assert args.profile == "exhaustive"


def test_exhaustive_wide_plc_profile_expands_core_memory_areas():
    diagnostic = _load_hmi_manual_diagnostic()

    ranges = diagnostic._wide_ranges(include_volatile=False, profile="exhaustive")

    assert ("DM", "D", 0, 32768) in ranges
    assert ("CIO", "CIO", 0, 6144) in ranges
    assert ("WR", "W", 0, 512) in ranges
    assert ("HR", "H", 0, 512) in ranges


def test_burst_ranges_focus_on_hmi_outputs_and_initial_cio():
    diagnostic = _load_hmi_manual_diagnostic()

    assert ("HR", "H", 0, 43) in diagnostic.BURST_TRACE_RANGES
    assert ("WR", "W", 0, 14) in diagnostic.BURST_TRACE_RANGES
    assert ("WR", "W", 400, 4) in diagnostic.BURST_TRACE_RANGES
    assert ("CIO", "CIO", 0, 129) in diagnostic.BURST_TRACE_RANGES
    assert ("DM", "D", 1008, 2) in diagnostic.BURST_TRACE_RANGES
    assert ("DM", "D", 3630, 2) in diagnostic.BURST_TRACE_RANGES


def test_parser_accepts_full_diff_mode():
    diagnostic = _load_hmi_manual_diagnostic()
    args = diagnostic.build_parser().parse_args(
        ["poll-plc", "--samples", "2", "--interval-seconds", "2", "--full", "--diff"]
    )

    assert args.full is True
    assert args.diff is True


def test_parser_accepts_burst_plc_mode():
    diagnostic = _load_hmi_manual_diagnostic()
    args = diagnostic.build_parser().parse_args(
        [
            "burst-plc",
            "--duration-seconds",
            "20",
            "--interval-ms",
            "100",
            "--local-port",
            "9600",
            "--cio-start",
            "0",
            "--cio-words",
            "256",
        ]
    )

    assert args.duration_seconds == 20
    assert args.interval_ms == 100
    assert args.local_port == 9600
    assert args.cio_start == 0
    assert args.cio_words == 256


def test_parser_accepts_dm_strings_preset():
    diagnostic = _load_hmi_manual_diagnostic()
    args = diagnostic.build_parser().parse_args(
        ["dm-strings", "--preset", "hmi-names", "--limit", "5"]
    )

    assert args.preset == "hmi-names"
    assert args.limit == 5


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
