"""Passive diagnostics for HMI manual section visibility.

This tool is intentionally read-only. The Raspberry Pi side samples PLC memory
with FINS memory-read commands only; the Lenovo side inspects persisted SQLite
state. It is meant to prove where an HMI manual activation is lost before any
semantic correction is made.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from acquisition.decoders import get_bit, words
from model.database import create_db_engine
from model.json_columns import load_json_column

SECTION_COUNT = 112
HMI_SCREEN1_START = 0
HMI_H_WORD = 10
HMI_SCREEN2_START = 32
HMI_SCREEN_WORDS = 11
H_SECTION_START = 11
H_SECTION_WORDS = 21
H_AUTO_OFFSET = 0
H_MANUAL_OFFSET = 7
H_INTERNAL_OFFSET = 14
W_RESET_START = 1
W_SALIDA_START = 4
W_SALIDA_WORDS = 10
W_FOTOCELULA_START = 25
H_FOTOCELULA_START = 100
DM_CONTEXT_START = 100
DM_CONTEXT_WORDS = 17
DM_HMI1_INDEX_START = 1008
DM_HMI2_INDEX_START = 3630
FINS_CHUNK_WORDS = 900

WIDE_TRACE_RANGES: tuple[tuple[str, str, int, int], ...] = (
    ("HR", "H", 0, 43),
    ("HR", "H", 100, 1),
    ("WR", "W", 0, 501),
    ("DM", "D", 100, 17),
    ("DM", "D", 1000, 2652),
    ("DM", "D", 20000, 1),
    ("AR", "A", 200, 1),
    ("AR", "A", 401, 2),
    ("AR", "A", 450, 24),
    ("AR", "A", 500, 1),
    ("CIO", "CIO", 0, 501),
)

WIDE_EXHAUSTIVE_RANGES: tuple[tuple[str, str, int, int], ...] = (
    ("HR", "H", 0, 512),
    ("WR", "W", 0, 512),
    ("CIO", "CIO", 0, 6144),
    ("AR", "A", 0, 960),
    ("DM", "D", 0, 32768),
)

BURST_TRACE_RANGES: tuple[tuple[str, str, int, int], ...] = (
    ("HR", "H", 0, 43),
    ("WR", "W", 0, 14),
    ("WR", "W", 25, 1),
    ("WR", "W", 400, 4),
    ("CIO", "CIO", 0, 129),
    ("DM", "D", 100, 17),
    ("DM", "D", 1008, 2),
    ("DM", "D", 3630, 2),
)

WIDE_VOLATILE_RANGES: tuple[tuple[str, str, int, int], ...] = (
    ("DM", "D", 500, 21),
    ("AR", "A", 262, 3),
    ("AR", "A", 351, 3),
)

MIN_BURST_INTERVAL_MS = 100.0

WIDE_PROFILES: dict[str, tuple[tuple[str, str, int, int], ...]] = {
    "standard": WIDE_TRACE_RANGES,
    "exhaustive": WIDE_EXHAUSTIVE_RANGES,
}

KNOWN_VOLATILE_RANGES: tuple[tuple[str, int, int, str], ...] = (
    ("A", 0, 2, "auxiliary system counters seen changing every sample"),
    ("A", 262, 266, "PLC cycle-time diagnostics"),
    ("A", 351, 353, "AR PLC clock"),
    ("D", 500, 520, "DM PLC/display clock"),
    ("W", 0, 0, "oscillator flags; W0.01=fsdecseg in Tabla_ES.html"),
)

DM_STRING_PRESETS: dict[str, tuple[int, int, int, int]] = {
    # Tabla_ES.html: STRING slots from D1010 through D3620, spaced every 10 words.
    # D1008/D1009 and D3630..D3651 are INTs, not strings.
    "hmi-names": (1010, 262, 10, 5),
}


def _valid_section(value: str) -> int:
    section = int(value)
    if not 1 <= section <= SECTION_COUNT:
        raise argparse.ArgumentTypeError(f"section must be 1..{SECTION_COUNT}")
    return section


def _section_bit(raw_words: list[int], group_offset: int, section_id: int) -> bool:
    idx = section_id - 1
    return get_bit(raw_words[group_offset + idx // 16], idx % 16)


def _section_source(base_word: int, section_id: int) -> str:
    idx = section_id - 1
    return f"H{base_word + idx // 16}.{idx % 16:02d}"


def _section_flags(h11_h31_raw: list[int], w4_w13_raw: list[int], section_id: int) -> dict[str, Any]:
    return {
        "id": section_id,
        "automatico_calculado": _section_bit(h11_h31_raw, H_AUTO_OFFSET, section_id),
        "automatico_source": _section_source(11, section_id),
        "manual_activo": _section_bit(h11_h31_raw, H_MANUAL_OFFSET, section_id),
        "manual_source": _section_source(18, section_id),
        "salida_interna": _section_bit(h11_h31_raw, H_INTERNAL_OFFSET, section_id),
        "salida_interna_source": _section_source(25, section_id),
    }


def _active_ids(sections: list[dict[str, Any]], field: str) -> list[int]:
    return [section["id"] for section in sections if section[field]]


def _range_text(values: list[int]) -> str:
    if not values:
        return "-"
    ranges = []
    start = prev = values[0]
    for value in values[1:]:
        if value == prev + 1:
            prev = value
            continue
        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = value
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(ranges)


def _hmi_screen_state(raw_word: int, selected: int, previous: int, prefix: str) -> dict[str, Any]:
    selected_ui = selected + 1 if 0 <= selected < SECTION_COUNT else None
    previous_ui = previous + 1 if 0 <= previous < SECTION_COUNT else None
    return {
        "raw_word": raw_word,
        "raw_word_hex": f"0x{raw_word & 0xFFFF:04X}",
        "indice_seccion_raw": selected,
        "seccion_ui": selected_ui,
        "indice_anterior_raw": previous,
        "seccion_anterior_ui": previous_ui,
        "automatico_seccion_seleccionada": get_bit(raw_word, 12),
        "manual_seccion_seleccionada": get_bit(raw_word, 13),
        "orden_transferencia_comun": get_bit(raw_word, 14),
        "indicacion_activacion_alumbrado_seccion": get_bit(raw_word, 15),
        "source_word": prefix,
    }


def _context_state(
    *,
    w1_raw: int | None = None,
    h100_raw: int | None = None,
    w25_raw: int | None = None,
    d100_d116_raw: list[int] | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if w1_raw is not None:
        context["W1"] = {
            "raw": w1_raw,
            "raw_hex": f"0x{w1_raw & 0xFFFF:04X}",
            "horario_global_activo": get_bit(w1_raw, 1),
            "reset_temporizado_activo": get_bit(w1_raw, 2),
        }
    if h100_raw is not None:
        context["H100"] = {
            "raw": h100_raw,
            "raw_hex": f"0x{h100_raw & 0xFFFF:04X}",
            "fotocelula_mem_fun": get_bit(h100_raw, 0),
            "fotocelula_filtrada_activa": get_bit(h100_raw, 1),
        }
    if w25_raw is not None:
        context["W25"] = {
            "raw": w25_raw,
            "raw_hex": f"0x{w25_raw & 0xFFFF:04X}",
            "fotocelula_entrada_raw": get_bit(w25_raw, 0),
        }
    if d100_d116_raw is not None:
        if len(d100_d116_raw) != DM_CONTEXT_WORDS:
            raise ValueError(f"D100..D116 requires {DM_CONTEXT_WORDS} words")
        context["D100_D116"] = {
            "raw_words": d100_d116_raw,
            "D106_contador_apagados": d100_d116_raw[6],
            "D116_modfunalu": d100_d116_raw[16],
        }
    return context


def decode_plc_snapshot(
    *,
    h10_raw: int,
    d1008: int,
    d1009: int,
    h11_h31_raw: list[int],
    w4_w13_raw: list[int],
    h42_raw: int | None = None,
    d3630: int | None = None,
    d3631: int | None = None,
    h0_h10_raw: list[int] | None = None,
    h32_h42_raw: list[int] | None = None,
    w1_raw: int | None = None,
    h100_raw: int | None = None,
    w25_raw: int | None = None,
    d100_d116_raw: list[int] | None = None,
    timestamp_utc: datetime | None = None,
    selected_section: int | None = None,
) -> dict[str, Any]:
    if len(h11_h31_raw) != H_SECTION_WORDS:
        raise ValueError(f"H11..H31 requires {H_SECTION_WORDS} words")
    if len(w4_w13_raw) != W_SALIDA_WORDS:
        raise ValueError(f"W4..W13 requires {W_SALIDA_WORDS} words")
    if h0_h10_raw is not None and len(h0_h10_raw) != HMI_SCREEN_WORDS:
        raise ValueError(f"H0..H10 requires {HMI_SCREEN_WORDS} words")
    if h32_h42_raw is not None and len(h32_h42_raw) != HMI_SCREEN_WORDS:
        raise ValueError(f"H32..H42 requires {HMI_SCREEN_WORDS} words")

    timestamp_utc = timestamp_utc or datetime.now(timezone.utc)
    hmi_section = d1008 + 1 if 0 <= d1008 < SECTION_COUNT else None
    hmi_previous = d1009 + 1 if 0 <= d1009 < SECTION_COUNT else None
    target_id = selected_section or hmi_section
    sections = [
        _section_flags(h11_h31_raw, w4_w13_raw, section_id)
        for section_id in range(1, SECTION_COUNT + 1)
    ]
    target = sections[target_id - 1] if target_id is not None and 1 <= target_id <= SECTION_COUNT else None

    auto_ids = _active_ids(sections, "automatico_calculado")
    manual_ids = _active_ids(sections, "manual_activo")
    internal_ids = _active_ids(sections, "salida_interna")

    snapshot = {
        "timestamp_utc": timestamp_utc.isoformat(),
        "hmi_original": {
            "h10_raw": h10_raw,
            "h10_raw_hex": f"0x{h10_raw & 0xFFFF:04X}",
            "indice_seccion_raw": d1008,
            "seccion_ui_from_d1008": hmi_section,
            "indice_anterior_raw": d1009,
            "seccion_anterior_ui_from_d1009": hmi_previous,
            "automatico_seccion_seleccionada": get_bit(h10_raw, 12),
            "manual_seccion_seleccionada": get_bit(h10_raw, 13),
            "orden_transferencia_comun": get_bit(h10_raw, 14),
            "indicacion_activacion_alumbrado_seccion": get_bit(h10_raw, 15),
        },
        "target_section": target,
        "counts": {
            "automatico_calculado": len(auto_ids),
            "manual_activo": len(manual_ids),
            "salida_interna": len(internal_ids),
        },
        "active_ids": {
            "automatico_calculado": auto_ids,
            "manual_activo": manual_ids,
            "salida_interna": internal_ids,
        },
        "raw_words": {
            "H10": h10_raw,
            "D1008_D1009": [d1008, d1009],
            "H11_H31": h11_h31_raw,
            "W4_W13": w4_w13_raw,
        },
    }
    if h42_raw is not None and d3630 is not None and d3631 is not None:
        snapshot["hmi_screen_2"] = _hmi_screen_state(h42_raw, d3630, d3631, "H42")
        snapshot["raw_words"]["H42"] = h42_raw
        snapshot["raw_words"]["D3630_D3631"] = [d3630, d3631]
    if h0_h10_raw is not None:
        snapshot["raw_words"]["H0_H10"] = h0_h10_raw
    if h32_h42_raw is not None:
        snapshot["raw_words"]["H32_H42"] = h32_h42_raw
    context = _context_state(
        w1_raw=w1_raw,
        h100_raw=h100_raw,
        w25_raw=w25_raw,
        d100_d116_raw=d100_d116_raw,
    )
    if context:
        snapshot["context"] = context
        if w1_raw is not None:
            snapshot["raw_words"]["W1"] = w1_raw
        if h100_raw is not None:
            snapshot["raw_words"]["H100"] = h100_raw
        if w25_raw is not None:
            snapshot["raw_words"]["W25"] = w25_raw
        if d100_d116_raw is not None:
            snapshot["raw_words"]["D100_D116"] = d100_d116_raw
    return snapshot


def _format_bool(value: Any) -> str:
    return "ON" if value else "off"


def format_plc_snapshot(snapshot: dict[str, Any], *, show_raw: bool = False) -> str:
    hmi = snapshot["hmi_original"]
    target = snapshot["target_section"]
    counts = snapshot["counts"]
    active_ids = snapshot["active_ids"]
    lines = [
        f"timestamp_utc: {snapshot['timestamp_utc']}",
        (
            "HMI: "
            f"D1008={hmi['indice_seccion_raw']} -> seccion_ui={hmi['seccion_ui_from_d1008']} | "
            f"D1009={hmi['indice_anterior_raw']} -> seccion_ui={hmi['seccion_anterior_ui_from_d1009']} | "
            f"H10={hmi['h10_raw_hex']}"
        ),
        (
            "H10 flags: "
            f"auto_sel={_format_bool(hmi['automatico_seccion_seleccionada'])} "
            f"manual_sel={_format_bool(hmi['manual_seccion_seleccionada'])} "
            f"transfer={_format_bool(hmi['orden_transferencia_comun'])} "
            f"ind_act={_format_bool(hmi['indicacion_activacion_alumbrado_seccion'])}"
        ),
    ]
    screen_2 = snapshot.get("hmi_screen_2")
    if screen_2:
        lines.extend(
            [
                (
                    "HMI screen2: "
                    f"D3630={screen_2['indice_seccion_raw']} -> seccion_ui={screen_2['seccion_ui']} | "
                    f"D3631={screen_2['indice_anterior_raw']} -> seccion_ui={screen_2['seccion_anterior_ui']} | "
                    f"H42={screen_2['raw_word_hex']}"
                ),
                (
                    "H42 flags: "
                    f"auto_sel={_format_bool(screen_2['automatico_seccion_seleccionada'])} "
                    f"manual_sel={_format_bool(screen_2['manual_seccion_seleccionada'])} "
                    f"transfer={_format_bool(screen_2['orden_transferencia_comun'])} "
                    f"ind_act={_format_bool(screen_2['indicacion_activacion_alumbrado_seccion'])}"
                ),
            ]
        )
    if target is None:
        lines.append("target_section: none (D1008 fuera de 0..111 y no se paso --section)")
    else:
        lines.append(
            "target_section "
            f"{target['id']}: "
            f"auto={_format_bool(target['automatico_calculado'])} ({target['automatico_source']}) | "
            f"manual={_format_bool(target['manual_activo'])} ({target['manual_source']}) | "
            f"interna={_format_bool(target['salida_interna'])} ({target['salida_interna_source']})"
        )
    lines.extend(
        [
            (
                "counts: "
                f"auto={counts['automatico_calculado']} "
                f"manual={counts['manual_activo']} "
                f"interna={counts['salida_interna']}"
            ),
            (
                "active_ids: "
                f"manual={_range_text(active_ids['manual_activo'])} | "
                f"interna={_range_text(active_ids['salida_interna'])}"
            ),
        ]
    )
    context = snapshot.get("context", {})
    if context:
        context_parts = []
        if "W1" in context:
            w1 = context["W1"]
            context_parts.append(
                f"W1={w1['raw_hex']} horario={_format_bool(w1['horario_global_activo'])} "
                f"reset={_format_bool(w1['reset_temporizado_activo'])}"
            )
        if "H100" in context:
            h100 = context["H100"]
            context_parts.append(
                f"H100={h100['raw_hex']} foto_filtrada={_format_bool(h100['fotocelula_filtrada_activa'])}"
            )
        if "W25" in context:
            w25 = context["W25"]
            context_parts.append(
                f"W25={w25['raw_hex']} foto_raw={_format_bool(w25['fotocelula_entrada_raw'])}"
            )
        if "D100_D116" in context:
            dm = context["D100_D116"]
            context_parts.append(
                f"D106={dm['D106_contador_apagados']} D116={dm['D116_modfunalu']}"
            )
        lines.append("context: " + " | ".join(context_parts))
    if show_raw:
        raw = snapshot["raw_words"]
        lines.extend(
            [
                f"raw H11..H31: {raw['H11_H31']}",
                f"raw W4..W13: {raw['W4_W13']}",
            ]
        )
        if "H0_H10" in raw:
            lines.append(f"raw H0..H10: {raw['H0_H10']}")
        if "H32_H42" in raw:
            lines.append(f"raw H32..H42: {raw['H32_H42']}")
        if "D100_D116" in raw:
            lines.append(f"raw D100..D116: {raw['D100_D116']}")
    return "\n".join(lines)


def _delta(prev_values: list[int], curr_values: list[int]) -> tuple[list[int], list[int]]:
    prev = set(prev_values)
    curr = set(curr_values)
    return sorted(curr - prev), sorted(prev - curr)


def _format_delta(label: str, prev_values: list[int], curr_values: list[int]) -> str | None:
    added, removed = _delta(prev_values, curr_values)
    if not added and not removed:
        return None
    return f"changed {label}: added={_range_text(added)} removed={_range_text(removed)}"


def _format_value_change(label: str, old: Any, new: Any) -> str | None:
    if old == new:
        return None
    return f"changed {label}: {old} -> {new}"


def _word_bit_delta(old: int, new: int) -> tuple[list[int], list[int]]:
    added = []
    removed = []
    for bit in range(16):
        was = get_bit(old, bit)
        now = get_bit(new, bit)
        if now and not was:
            added.append(bit)
        elif was and not now:
            removed.append(bit)
    return added, removed


def format_word_change(address: str, old: int, new: int) -> str:
    added, removed = _word_bit_delta(old, new)
    bits = ""
    if added or removed:
        bits = f" bits added={_range_text(added)} removed={_range_text(removed)}"
    return (
        f"{address}: {old} -> {new} "
        f"(0x{old & 0xFFFF:04X} -> 0x{new & 0xFFFF:04X}){bits}"
    )


def _split_address(address: str) -> tuple[str, int]:
    for idx, char in enumerate(address):
        if char.isdigit():
            return address[:idx], int(address[idx:])
    raise ValueError(f"direccion sin indice numerico: {address}")


def is_known_volatile_address(address: str) -> bool:
    prefix, index = _split_address(address)
    return any(
        prefix == volatile_prefix and start <= index <= end
        for volatile_prefix, start, end, _reason in KNOWN_VOLATILE_RANGES
    )


def filter_known_volatiles(snapshot: dict[str, int]) -> dict[str, int]:
    return {
        address: value
        for address, value in snapshot.items()
        if not is_known_volatile_address(address)
    }


def decode_ascii_words(raw_words: list[int]) -> str:
    data = bytearray()
    for word in raw_words:
        data.append((word >> 8) & 0xFF)
        data.append(word & 0xFF)
    return bytes(data).split(b"\x00", 1)[0].decode("latin-1", errors="replace").rstrip()


def format_raw_words(raw_words: list[int]) -> str:
    return "[" + ", ".join(f"0x{word & 0xFFFF:04X}" for word in raw_words) + "]"


def _hmi_diff_lines(label: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> list[str]:
    if old is None and new is None:
        return []
    if old is None:
        return [f"changed {label}: absent -> present"]
    if new is None:
        return [f"changed {label}: present -> absent"]
    lines = []
    for field in [
        "raw_word_hex",
        "indice_seccion_raw",
        "seccion_ui",
        "manual_seccion_seleccionada",
        "indicacion_activacion_alumbrado_seccion",
    ]:
        line = _format_value_change(f"{label}.{field}", old.get(field), new.get(field))
        if line:
            lines.append(line)
    return lines


def _context_diff_lines(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    lines = []
    for group, fields in {
        "W1": ["raw_hex", "horario_global_activo", "reset_temporizado_activo"],
        "H100": ["raw_hex", "fotocelula_filtrada_activa"],
        "W25": ["raw_hex", "fotocelula_entrada_raw"],
        "D100_D116": ["D106_contador_apagados", "D116_modfunalu"],
    }.items():
        old_group = old.get(group, {})
        new_group = new.get(group, {})
        for field in fields:
            line = _format_value_change(
                f"{group}.{field}",
                old_group.get(field),
                new_group.get(field),
            )
            if line:
                lines.append(line)
    return lines


def format_plc_diff(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    if previous is None:
        return format_plc_snapshot(current)
    lines = [f"timestamp_utc: {current['timestamp_utc']}"]
    for field in ["manual_activo", "salida_interna"]:
        line = _format_delta(
            field,
            previous["active_ids"][field],
            current["active_ids"][field],
        )
        if line:
            lines.append(line)
    lines.extend(_hmi_diff_lines("screen1", previous.get("hmi_original"), current.get("hmi_original")))
    lines.extend(_hmi_diff_lines("screen2", previous.get("hmi_screen_2"), current.get("hmi_screen_2")))
    lines.extend(_context_diff_lines(previous.get("context", {}), current.get("context", {})))
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def _validate_fins_config(local_port: int | None = None) -> None:
    from config.settings import Config

    if local_port is not None:
        Config.UDP_LOCAL_PORT = local_port
    Config.validate()
    if not Config.UDP_LOCAL_HOST.strip():
        raise SystemExit("UDP_LOCAL_HOST debe estar configurado para leer FINS")
    if Config.FINS_SOURCE_NODE == 0:
        raise SystemExit("FINS_SOURCE_NODE debe estar configurado para leer FINS")
    if Config.FINS_DEST_NODE == 0:
        raise SystemExit("FINS_DEST_NODE debe estar configurado para leer FINS")


def poll_plc(args: argparse.Namespace) -> int:
    from fins.client import FINSClient
    from fins.frame import FINSError

    if args.samples < 1:
        raise SystemExit("--samples debe ser >= 1")
    if args.samples > 1 and args.interval_seconds < 2.0:
        raise SystemExit("--interval-seconds no puede bajar de 2.0 contra PLC real")

    _validate_fins_config(args.local_port)
    with FINSClient() as client:
        previous_snapshot = None
        for sample in range(args.samples):
            try:
                h0_h10_raw = None
                h32_h42_raw = None
                h42_raw = None
                d3630 = None
                d3631 = None
                w1_raw = None
                h100_raw = None
                w25_raw = None
                d100_d116_raw = None
                if args.full:
                    h0_h10_raw = words(client.read_h_range(HMI_SCREEN1_START, HMI_SCREEN_WORDS))
                    h10_raw = h0_h10_raw[HMI_H_WORD - HMI_SCREEN1_START]
                    h32_h42_raw = words(client.read_h_range(HMI_SCREEN2_START, HMI_SCREEN_WORDS))
                    h42_raw = h32_h42_raw[42 - HMI_SCREEN2_START]
                    d3630, d3631 = words(client.read_dm_range(DM_HMI2_INDEX_START, 2))
                    w1_raw = words(client.read_w_range(W_RESET_START, 1))[0]
                    h100_raw = words(client.read_h_range(H_FOTOCELULA_START, 1))[0]
                    w25_raw = words(client.read_w_range(W_FOTOCELULA_START, 1))[0]
                    d100_d116_raw = words(client.read_dm_range(DM_CONTEXT_START, DM_CONTEXT_WORDS))
                else:
                    h10_raw = words(client.read_h_range(HMI_H_WORD, 1))[0]
                d1008, d1009 = words(client.read_dm_range(DM_HMI1_INDEX_START, 2))
                h11_h31_raw = words(client.read_h_range(H_SECTION_START, H_SECTION_WORDS))
                w4_w13_raw = words(client.read_w_range(W_SALIDA_START, W_SALIDA_WORDS))
                snapshot = decode_plc_snapshot(
                    h10_raw=h10_raw,
                    d1008=d1008,
                    d1009=d1009,
                    h11_h31_raw=h11_h31_raw,
                    w4_w13_raw=w4_w13_raw,
                    h42_raw=h42_raw,
                    d3630=d3630,
                    d3631=d3631,
                    h0_h10_raw=h0_h10_raw,
                    h32_h42_raw=h32_h42_raw,
                    w1_raw=w1_raw,
                    h100_raw=h100_raw,
                    w25_raw=w25_raw,
                    d100_d116_raw=d100_d116_raw,
                    timestamp_utc=datetime.now(timezone.utc),
                    selected_section=args.section,
                )
                if args.json:
                    print(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
                else:
                    output = (
                        format_plc_diff(previous_snapshot, snapshot)
                        if args.diff
                        else format_plc_snapshot(snapshot, show_raw=args.raw)
                    )
                    if output:
                        if args.samples > 1:
                            print(f"--- sample {sample + 1}/{args.samples} ---")
                        print(output)
                previous_snapshot = snapshot
            except (FINSError, OSError, RuntimeError, ValueError) as exc:
                error = {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "sample": sample + 1,
                    "error": str(exc),
                }
                if args.json:
                    print(json.dumps(error, ensure_ascii=False, sort_keys=True))
                else:
                    if args.samples > 1:
                        print(f"--- sample {sample + 1}/{args.samples} ---")
                    print(f"ERROR: {exc}")
            if sample < args.samples - 1:
                time.sleep(args.interval_seconds)
    return 0


def _read_words_chunked(client, area: str, start: int, count: int) -> list[int]:
    values: list[int] = []
    offset = 0
    while offset < count:
        chunk = min(FINS_CHUNK_WORDS, count - offset)
        values.extend(words(client.read_memory_area(area, start + offset, chunk)))
        offset += chunk
    return values


def read_range_snapshot(
    client,
    ranges: tuple[tuple[str, str, int, int], ...],
) -> dict[str, int]:
    snapshot: dict[str, int] = {}
    for area, prefix, start, count in ranges:
        values = _read_words_chunked(client, area, start, count)
        for offset, value in enumerate(values):
            snapshot[f"{prefix}{start + offset}"] = value
    return snapshot


def _wide_ranges(
    include_volatile: bool,
    profile: str = "standard",
) -> tuple[tuple[str, str, int, int], ...]:
    ranges = WIDE_PROFILES[profile]
    if include_volatile and profile == "standard":
        return ranges + WIDE_VOLATILE_RANGES
    return ranges


def read_wide_snapshot(
    client,
    include_volatile: bool = False,
    profile: str = "standard",
) -> dict[str, int]:
    return read_range_snapshot(client, _wide_ranges(include_volatile, profile))


def _changed_words(previous: dict[str, int], current: dict[str, int]) -> list[tuple[str, int, int]]:
    changes = []
    for address in sorted(current):
        old = previous.get(address)
        new = current[address]
        if old is None or old == new:
            continue
        changes.append((address, old, new))
    return changes


def format_wide_status(current: dict[str, int], *, limit: int) -> str:
    non_zero = [
        f"{address}=0x{value & 0xFFFF:04X}"
        for address, value in sorted(current.items())
        if value
    ]
    return (
        f"status: {len(current)} words leidos, {len(non_zero)} words no cero"
        + (f"\nnon_zero: {', '.join(non_zero[:limit])}" if non_zero else "")
    )


def format_wide_diff(
    previous: dict[str, int] | None,
    current: dict[str, int],
    *,
    limit: int,
) -> str:
    if previous is None:
        return "wide baseline\n" + format_wide_status(current, limit=limit)

    lines = []
    for address, old, new in _changed_words(previous, current):
        lines.append(format_word_change(address, old, new))
        if len(lines) >= limit:
            lines.append(f"... cambios truncados a --limit {limit}")
            break
    return "\n".join(lines)


def wide_plc(args: argparse.Namespace) -> int:
    from fins.client import FINSClient
    from fins.frame import FINSError

    if args.samples < 1:
        raise SystemExit("--samples debe ser >= 1")
    if args.samples > 1 and args.interval_seconds < 2.0:
        raise SystemExit("--interval-seconds no puede bajar de 2.0 contra PLC real")
    if args.profile == "exhaustive" and args.samples > 1 and args.interval_seconds < 5.0:
        raise SystemExit("--profile exhaustive requiere --interval-seconds >= 5.0")
    if args.limit < 1:
        raise SystemExit("--limit debe ser >= 1")

    _validate_fins_config(args.local_port)
    ranges = _wide_ranges(args.include_volatile, args.profile)
    total_words = sum(count for _, _, _, count in ranges)
    print(
        f"wide-plc read-only: profile={args.profile} {len(ranges)} rangos, "
        f"{total_words} words por muestra, interval={args.interval_seconds}s"
    )
    if not args.show_known_volatile:
        ignored = ", ".join(
            f"{prefix}{start}..{prefix}{end}"
            for prefix, start, end, _reason in KNOWN_VOLATILE_RANGES
        )
        print(f"known volatile suppressed in output: {ignored}")
    with FINSClient() as client:
        previous_snapshot = None
        for sample in range(args.samples):
            try:
                snapshot = read_wide_snapshot(
                    client,
                    include_volatile=args.include_volatile,
                    profile=args.profile,
                )
                visible_snapshot = (
                    snapshot if args.show_known_volatile else filter_known_volatiles(snapshot)
                )
                output = format_wide_diff(previous_snapshot, visible_snapshot, limit=args.limit)
                if (
                    not output
                    and args.status_every > 0
                    and (sample + 1) % args.status_every == 0
                ):
                    output = format_wide_status(visible_snapshot, limit=args.status_limit)
                if output:
                    print(f"--- sample {sample + 1}/{args.samples} ---")
                    print(output)
                previous_snapshot = visible_snapshot
            except (FINSError, OSError, RuntimeError, ValueError) as exc:
                print(f"--- sample {sample + 1}/{args.samples} ---")
                print(f"ERROR: {exc}")
            if sample < args.samples - 1:
                time.sleep(args.interval_seconds)
    return 0


def burst_plc(args: argparse.Namespace) -> int:
    from fins.client import FINSClient
    from fins.frame import FINSError

    if args.duration_seconds <= 0:
        raise SystemExit("--duration-seconds debe ser > 0")
    if args.interval_ms < MIN_BURST_INTERVAL_MS:
        raise SystemExit(f"--interval-ms no puede bajar de {MIN_BURST_INTERVAL_MS:.0f}")
    if args.limit < 1:
        raise SystemExit("--limit debe ser >= 1")
    if args.cio_words < 1:
        raise SystemExit("--cio-words debe ser >= 1")
    if args.cio_start < 0:
        raise SystemExit("--cio-start debe ser >= 0")

    _validate_fins_config(args.local_port)
    ranges = tuple(
        (area, prefix, args.cio_start, args.cio_words)
        if area == "CIO" and prefix == "CIO"
        else (area, prefix, start, count)
        for area, prefix, start, count in BURST_TRACE_RANGES
    )
    total_words = sum(count for _, _, _, count in ranges)
    interval_seconds = args.interval_ms / 1000.0
    print(
        f"burst-plc read-only: {len(ranges)} rangos, {total_words} words por muestra, "
        f"duration={args.duration_seconds}s interval={interval_seconds:.3f}s"
    )
    if not args.show_known_volatile:
        ignored = ", ".join(
            f"{prefix}{start}..{prefix}{end}"
            for prefix, start, end, _reason in KNOWN_VOLATILE_RANGES
        )
        print(f"known volatile suppressed in output: {ignored}")
    print("accion esperada: ejecutar OFF -> ON -> OFF manual en HMI mientras corre esta traza")

    with FINSClient() as client:
        previous_snapshot = None
        started = time.monotonic()
        next_status = started + args.status_every_seconds
        sample = 0
        while True:
            now = time.monotonic()
            if sample > 0 and now - started >= args.duration_seconds:
                break
            sample += 1
            try:
                snapshot = read_range_snapshot(client, ranges)
                visible_snapshot = (
                    snapshot if args.show_known_volatile else filter_known_volatiles(snapshot)
                )
                output = format_wide_diff(previous_snapshot, visible_snapshot, limit=args.limit)
                now = time.monotonic()
                if (
                    not output
                    and args.status_every_seconds > 0
                    and now >= next_status
                ):
                    output = format_wide_status(visible_snapshot, limit=args.status_limit)
                    next_status = now + args.status_every_seconds
                if output:
                    print(f"--- t=+{now - started:.3f}s sample={sample} ---")
                    print(output)
                previous_snapshot = visible_snapshot
            except (FINSError, OSError, RuntimeError, ValueError) as exc:
                now = time.monotonic()
                print(f"--- t=+{now - started:.3f}s sample={sample} ---")
                print(f"ERROR: {exc}")
            sleep_for = started + sample * interval_seconds - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
    return 0


def dm_strings(args: argparse.Namespace) -> int:
    from fins.client import FINSClient

    preset = DM_STRING_PRESETS.get(args.preset) if args.preset else None
    start = args.start
    items = args.items
    stride = args.stride
    words_per_string = args.words_per_string
    if preset and start is None and items is None:
        start, items, stride, words_per_string = preset
    if start is None or items is None:
        raise SystemExit("dm-strings requiere --preset o --start y --items")
    if items < 1:
        raise SystemExit("--items debe ser >= 1")
    if words_per_string < 1:
        raise SystemExit("--words-per-string debe ser >= 1")
    if stride < words_per_string:
        raise SystemExit("--stride debe ser >= --words-per-string")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit debe ser >= 1")

    _validate_fins_config(args.local_port)
    total_words = (items - 1) * stride + words_per_string
    with FINSClient() as client:
        raw = _read_words_chunked(client, "DM", start, total_words)

    print(
        f"dm-strings read-only: start=D{start} items={items} stride={stride} "
        f"words_per_string={words_per_string}"
    )
    print("idx | address | text | raw")
    printed = 0
    for index in range(items):
        offset = index * stride
        raw_words = raw[offset: offset + words_per_string]
        text_value = decode_ascii_words(raw_words)
        if not text_value and not args.include_empty:
            continue
        print(
            f"{index + 1} | D{start + offset} | "
            f"{text_value or '-'} | {format_raw_words(raw_words)}"
        )
        printed += 1
        if args.limit is not None and printed >= args.limit:
            print(f"... strings truncados a --limit {args.limit}")
            break
    return 0


def _bool_text(value: Any) -> str:
    if value is None:
        return "?"
    return "1" if bool(value) else "0"


def _print_cycle_rows(rows) -> None:
    print(
        "id | timestamp | fins_ok | sec_status | hmi_sec | h10 | "
        "h10_manual | h10_ind | manual_count | interna_count"
    )
    for row in rows:
        hmi_sec = None
        if row["indice_seccion"] is not None and 0 <= int(row["indice_seccion"]) < SECTION_COUNT:
            hmi_sec = int(row["indice_seccion"]) + 1
        h10_raw = row["h10_raw"]
        h10_text = "-" if h10_raw is None else f"0x{int(h10_raw) & 0xFFFF:04X}"
        print(
            f"{row['id']} | {row['timestamp']} | {_bool_text(row['fins_ok'])} | "
            f"{row['secciones_status']} | {hmi_sec or '-'} | {h10_text} | "
            f"{_bool_text(row['manual_seccion_seleccionada'])} | "
            f"{_bool_text(row['indicacion_activacion_alumbrado_seccion'])} | "
            f"{row['manual_count']} | {row['interna_count']}"
        )


def _print_section_rows(rows, section_id: int) -> None:
    print(f"\nsection {section_id} history")
    print("id | timestamp | auto | manual | interna | hmi_sec | h10_manual | h10_ind")
    for row in rows:
        hmi_sec = None
        if row["indice_seccion"] is not None and 0 <= int(row["indice_seccion"]) < SECTION_COUNT:
            hmi_sec = int(row["indice_seccion"]) + 1
        print(
            f"{row['id']} | {row['timestamp']} | "
            f"{_bool_text(row['automatico_calculado'])} | {_bool_text(row['manual_activo'])} | "
            f"{_bool_text(row['salida_interna'])} | "
            f"{hmi_sec or '-'} | {_bool_text(row['manual_seccion_seleccionada'])} | "
            f"{_bool_text(row['indicacion_activacion_alumbrado_seccion'])}"
        )


def inspect_db(args: argparse.Namespace) -> int:
    from config.settings import Config

    Config._validate_db()
    engine = create_db_engine(Config.DB_ESTADOS_URL)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                select
                    c.id,
                    c.timestamp,
                    c.fins_ok,
                    c.secciones_status,
                    h.indice_seccion,
                    h.h10_raw,
                    h.manual_seccion_seleccionada,
                    h.indicacion_activacion_alumbrado_seccion,
                    coalesce(sum(case when s.manual_activo then 1 else 0 end), 0) as manual_count,
                    coalesce(sum(case when s.salida_interna then 1 else 0 end), 0) as interna_count
                from ciclo c
                left join seccion_estado s on s.ciclo_id = c.id
                left join hmi_original_state h on h.ciclo_id = c.id
                group by
                    c.id, c.timestamp, c.fins_ok, c.secciones_status,
                    h.indice_seccion, h.h10_raw, h.manual_seccion_seleccionada,
                    h.indicacion_activacion_alumbrado_seccion
                order by c.id desc
                limit :limit
                """
            ),
            {"limit": args.limit},
        ).mappings().all()
        _print_cycle_rows(rows)

        if args.section:
            section_rows = conn.execute(
                text(
                    """
                    select
                        c.id,
                        c.timestamp,
                        s.automatico_calculado,
                        s.manual_activo,
                        s.salida_interna,
                        h.indice_seccion,
                        h.manual_seccion_seleccionada,
                        h.indicacion_activacion_alumbrado_seccion
                    from ciclo c
                    join seccion_estado s on s.ciclo_id = c.id
                    left join hmi_original_state h on h.ciclo_id = c.id
                    where s.seccion_id = :section
                    order by c.id desc
                    limit :limit
                    """
                ),
                {"section": args.section, "limit": args.limit},
            ).mappings().all()
            _print_section_rows(section_rows, args.section)

        if args.raw:
            raw_rows = conn.execute(
                text(
                    """
                    select c.id, sw.raw_words
                    from ciclo c
                    join vector_salidas_logicas_state sw on sw.ciclo_id = c.id
                    order by c.id desc
                    limit :limit
                    """
                ),
                {"limit": args.limit},
            ).mappings().all()
            print("\nraw W4..W13 by cycle")
            for row in raw_rows:
                print(f"{row['id']} | {load_json_column(row['raw_words'])}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only HMI manual visibility diagnostics"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    poll_parser = subparsers.add_parser("poll-plc")
    poll_parser.add_argument("--section", type=_valid_section)
    poll_parser.add_argument("--samples", type=int, default=1)
    poll_parser.add_argument("--interval-seconds", type=float, default=2.0)
    poll_parser.add_argument("--local-port", type=int)
    poll_parser.add_argument("--full", action="store_true")
    poll_parser.add_argument("--diff", action="store_true")
    poll_parser.add_argument("--json", action="store_true")
    poll_parser.add_argument("--raw", action="store_true")
    poll_parser.set_defaults(func=poll_plc)

    wide_parser = subparsers.add_parser("wide-plc")
    wide_parser.add_argument("--samples", type=int, default=60)
    wide_parser.add_argument("--interval-seconds", type=float, default=5.0)
    wide_parser.add_argument("--local-port", type=int)
    wide_parser.add_argument("--limit", type=int, default=80)
    wide_parser.add_argument("--status-every", type=int, default=5)
    wide_parser.add_argument("--status-limit", type=int, default=20)
    wide_parser.add_argument("--include-volatile", action="store_true")
    wide_parser.add_argument("--show-known-volatile", action="store_true")
    wide_parser.add_argument(
        "--profile",
        choices=sorted(WIDE_PROFILES),
        default="standard",
        help=(
            "standard lee rangos conocidos; exhaustive barre CIO/WR/HR/AR/DM completos "
            "de forma pasiva"
        ),
    )
    wide_parser.set_defaults(func=wide_plc)

    burst_parser = subparsers.add_parser("burst-plc")
    burst_parser.add_argument("--duration-seconds", type=float, default=30.0)
    burst_parser.add_argument("--interval-ms", type=float, default=100.0)
    burst_parser.add_argument("--local-port", type=int)
    burst_parser.add_argument("--limit", type=int, default=120)
    burst_parser.add_argument("--status-every-seconds", type=float, default=5.0)
    burst_parser.add_argument("--status-limit", type=int, default=20)
    burst_parser.add_argument("--show-known-volatile", action="store_true")
    burst_parser.add_argument("--cio-start", type=int, default=0)
    burst_parser.add_argument("--cio-words", type=int, default=129)
    burst_parser.set_defaults(func=burst_plc)

    strings_parser = subparsers.add_parser("dm-strings")
    strings_parser.add_argument("--preset", choices=sorted(DM_STRING_PRESETS))
    strings_parser.add_argument("--start", type=int)
    strings_parser.add_argument("--items", type=int)
    strings_parser.add_argument("--stride", type=int, default=10)
    strings_parser.add_argument("--words-per-string", type=int, default=5)
    strings_parser.add_argument("--local-port", type=int)
    strings_parser.add_argument("--include-empty", action="store_true")
    strings_parser.add_argument("--limit", type=int)
    strings_parser.set_defaults(func=dm_strings)

    db_parser = subparsers.add_parser("inspect-db")
    db_parser.add_argument("--limit", type=int, default=10)
    db_parser.add_argument("--section", type=_valid_section)
    db_parser.add_argument("--raw", action="store_true")
    db_parser.set_defaults(func=inspect_db)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
