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
HMI_H_WORD = 10
H_SECTION_START = 11
H_SECTION_WORDS = 21
H_AUTO_OFFSET = 0
H_MANUAL_OFFSET = 7
H_INTERNAL_OFFSET = 14
W_SALIDA_START = 4
W_SALIDA_WORDS = 10


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


def _wr_source(section_id: int) -> str:
    idx = section_id - 1
    return f"W{W_SALIDA_START + idx // 16}.{idx % 16:02d}"


def _section_flags(h11_h31_raw: list[int], w4_w13_raw: list[int], section_id: int) -> dict[str, Any]:
    return {
        "id": section_id,
        "automatico_calculado": _section_bit(h11_h31_raw, H_AUTO_OFFSET, section_id),
        "automatico_source": _section_source(11, section_id),
        "manual_activo": _section_bit(h11_h31_raw, H_MANUAL_OFFSET, section_id),
        "manual_source": _section_source(18, section_id),
        "salida_interna": _section_bit(h11_h31_raw, H_INTERNAL_OFFSET, section_id),
        "salida_interna_source": _section_source(25, section_id),
        "salida_wr": get_bit(w4_w13_raw[(section_id - 1) // 16], (section_id - 1) % 16),
        "salida_wr_source": _wr_source(section_id),
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


def decode_plc_snapshot(
    *,
    h10_raw: int,
    d1008: int,
    d1009: int,
    h11_h31_raw: list[int],
    w4_w13_raw: list[int],
    timestamp_utc: datetime | None = None,
    selected_section: int | None = None,
) -> dict[str, Any]:
    if len(h11_h31_raw) != H_SECTION_WORDS:
        raise ValueError(f"H11..H31 requires {H_SECTION_WORDS} words")
    if len(w4_w13_raw) != W_SALIDA_WORDS:
        raise ValueError(f"W4..W13 requires {W_SALIDA_WORDS} words")

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
    wr_ids = _active_ids(sections, "salida_wr")

    return {
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
            "salida_wr": len(wr_ids),
        },
        "active_ids": {
            "automatico_calculado": auto_ids,
            "manual_activo": manual_ids,
            "salida_interna": internal_ids,
            "salida_wr": wr_ids,
        },
        "raw_words": {
            "H10": h10_raw,
            "D1008_D1009": [d1008, d1009],
            "H11_H31": h11_h31_raw,
            "W4_W13": w4_w13_raw,
        },
    }


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
    if target is None:
        lines.append("target_section: none (D1008 fuera de 0..111 y no se paso --section)")
    else:
        lines.append(
            "target_section "
            f"{target['id']}: "
            f"auto={_format_bool(target['automatico_calculado'])} ({target['automatico_source']}) | "
            f"manual={_format_bool(target['manual_activo'])} ({target['manual_source']}) | "
            f"interna={_format_bool(target['salida_interna'])} ({target['salida_interna_source']}) | "
            f"wr={_format_bool(target['salida_wr'])} ({target['salida_wr_source']})"
        )
    lines.extend(
        [
            (
                "counts: "
                f"auto={counts['automatico_calculado']} "
                f"manual={counts['manual_activo']} "
                f"interna={counts['salida_interna']} "
                f"wr={counts['salida_wr']}"
            ),
            (
                "active_ids: "
                f"manual={_range_text(active_ids['manual_activo'])} | "
                f"interna={_range_text(active_ids['salida_interna'])} | "
                f"wr={_range_text(active_ids['salida_wr'])}"
            ),
        ]
    )
    if show_raw:
        raw = snapshot["raw_words"]
        lines.extend(
            [
                f"raw H11..H31: {raw['H11_H31']}",
                f"raw W4..W13: {raw['W4_W13']}",
            ]
        )
    return "\n".join(lines)


def _validate_fins_config() -> None:
    from config.settings import Config

    Config.validate()
    if not Config.UDP_LOCAL_HOST.strip():
        raise SystemExit("UDP_LOCAL_HOST debe estar configurado para leer FINS")
    if Config.FINS_SOURCE_NODE == 0:
        raise SystemExit("FINS_SOURCE_NODE debe estar configurado para leer FINS")
    if Config.FINS_DEST_NODE == 0:
        raise SystemExit("FINS_DEST_NODE debe estar configurado para leer FINS")


def poll_plc(args: argparse.Namespace) -> int:
    from fins.client import FINSClient

    if args.samples < 1:
        raise SystemExit("--samples debe ser >= 1")
    if args.samples > 1 and args.interval_seconds < 2.0:
        raise SystemExit("--interval-seconds no puede bajar de 2.0 contra PLC real")

    _validate_fins_config()
    with FINSClient() as client:
        for sample in range(args.samples):
            h10_raw = words(client.read_h_range(HMI_H_WORD, 1))[0]
            d1008, d1009 = words(client.read_dm_range(1008, 2))
            h11_h31_raw = words(client.read_h_range(H_SECTION_START, H_SECTION_WORDS))
            w4_w13_raw = words(client.read_w_range(W_SALIDA_START, W_SALIDA_WORDS))
            snapshot = decode_plc_snapshot(
                h10_raw=h10_raw,
                d1008=d1008,
                d1009=d1009,
                h11_h31_raw=h11_h31_raw,
                w4_w13_raw=w4_w13_raw,
                timestamp_utc=datetime.now(timezone.utc),
                selected_section=args.section,
            )
            if args.json:
                print(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
            else:
                if args.samples > 1:
                    print(f"--- sample {sample + 1}/{args.samples} ---")
                print(format_plc_snapshot(snapshot, show_raw=args.raw))
            if sample < args.samples - 1:
                time.sleep(args.interval_seconds)
    return 0


def _bool_text(value: Any) -> str:
    if value is None:
        return "?"
    return "1" if bool(value) else "0"


def _print_cycle_rows(rows) -> None:
    print(
        "id | timestamp | fins_ok | sec_status | hmi_sec | h10 | "
        "h10_manual | h10_ind | manual_count | interna_count | wr_count"
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
            f"{row['manual_count']} | {row['interna_count']} | {row['wr_count']}"
        )


def _print_section_rows(rows, section_id: int) -> None:
    print(f"\nsection {section_id} history")
    print("id | timestamp | auto | manual | interna | wr | hmi_sec | h10_manual | h10_ind")
    for row in rows:
        hmi_sec = None
        if row["indice_seccion"] is not None and 0 <= int(row["indice_seccion"]) < SECTION_COUNT:
            hmi_sec = int(row["indice_seccion"]) + 1
        print(
            f"{row['id']} | {row['timestamp']} | "
            f"{_bool_text(row['automatico_calculado'])} | {_bool_text(row['manual_activo'])} | "
            f"{_bool_text(row['salida_interna'])} | {_bool_text(row['salida_wr'])} | "
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
                    coalesce(sum(case when s.salida_interna then 1 else 0 end), 0) as interna_count,
                    coalesce(sum(case when s.salida_wr then 1 else 0 end), 0) as wr_count
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
                        s.salida_wr,
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
                    join salidas_wr_state sw on sw.ciclo_id = c.id
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
    poll_parser.add_argument("--json", action="store_true")
    poll_parser.add_argument("--raw", action="store_true")
    poll_parser.set_defaults(func=poll_plc)

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
