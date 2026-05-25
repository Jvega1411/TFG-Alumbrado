"""Python checks used by Lenovo PowerShell deployment helpers."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def _safe_db_url(url: str) -> str:
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<configured>"


def _config():
    from config.settings import Config

    return Config


def _parse_ts(raw) -> datetime:
    ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _latest(conn):
    row = conn.execute(
        text(
            "select id,timestamp,fins_ok,fins_error,secciones_status,secciones_error "
            "from ciclo order by id desc limit 1"
        )
    ).mappings().first()
    if row is None:
        raise SystemExit("tabla ciclo vacia")
    ts = _parse_ts(row["timestamp"])
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    return row, ts, age


def effective_config(_args) -> int:
    Config = _config()
    Config.validate_mqtt()
    Config._validate_db()
    print(
        f"MQTT={Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT} "
        f"topic={Config.MQTT_TOPIC}"
    )
    print(f"DB={_safe_db_url(Config.DB_ESTADOS_URL)}")
    return 0


def mqtt_broker_host(_args) -> int:
    Config = _config()
    print(Config.MQTT_BROKER_HOST)
    return 0


def db_liveness(args) -> int:
    Config = _config()
    sample_wait_seconds = args.sample_wait_seconds
    if sample_wait_seconds <= 0:
        acquisition_wait = int(max(10, round(Config.ACQUISITION_INTERVAL_S * 3)))
        heartbeat_wait = int(round(Config.HEARTBEAT_INTERVAL_S * 1.25))
        sample_wait_seconds = max(acquisition_wait, heartbeat_wait)
        sample_wait_seconds = min(sample_wait_seconds, args.max_ingest_age_seconds)

    engine = create_engine(Config.DB_ESTADOS_URL)
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("select name from sqlite_master where type='table'"))
        }
        if "ciclo" not in tables:
            raise SystemExit("tabla ciclo no existe")
        count = conn.execute(text("select count(*) from ciclo")).scalar_one()
        if count < 1:
            raise SystemExit("tabla ciclo vacia")

        first, first_ts, first_age = _latest(conn)
        print(
            f"sample1 id={first['id']} ts={first['timestamp']} "
            f"age_s={first_age:.0f} wait_s={sample_wait_seconds}"
        )
        if first_age < -120:
            raise SystemExit(f"timestamp futuro en BD: age_s={first_age:.0f}")
        if first_age > args.max_age_seconds:
            raise SystemExit(
                f"datos obsoletos: {first_age:.0f}s > {args.max_age_seconds} s"
            )

        time.sleep(sample_wait_seconds)
        second, second_ts, second_age = _latest(conn)
        print(
            f"sample2 id={second['id']} ts={second['timestamp']} "
            f"age_s={second_age:.0f} fins_ok={second['fins_ok']} "
            f"secciones_status={second['secciones_status']}"
        )
        if second_age < -120:
            raise SystemExit(f"timestamp futuro en BD: age_s={second_age:.0f}")
        if second_age > args.max_ingest_age_seconds:
            raise SystemExit(
                f"ingesta sin datos frescos: "
                f"{second_age:.0f}s > {args.max_ingest_age_seconds} s"
            )
        if int(second["id"]) <= int(first["id"]):
            raise SystemExit(
                f"ingesta no avanza: id inicial={first['id']} id final={second['id']}"
            )
        if second_ts <= first_ts:
            raise SystemExit(
                f"timestamp no avanza: "
                f"ts inicial={first['timestamp']} ts final={second['timestamp']}"
            )
        if not second["fins_ok"]:
            raise SystemExit(f"ultimo ciclo FINS fallo: {second['fins_error']}")
        if second["secciones_status"] != "ok":
            raise SystemExit(
                f"secciones no ok: "
                f"{second['secciones_status']} {second['secciones_error']}"
            )
    return 0


def inspect_config(_args) -> int:
    Config = _config()
    print("DB_ESTADOS_URL=", _safe_db_url(Config.DB_ESTADOS_URL))
    print("MQTT_BROKER=", f"{Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
    print("MQTT_TOPIC=", Config.MQTT_TOPIC)
    print("API=", f"{Config.API_HOST}:{Config.API_PORT}")
    return 0


def recent_cycles(args) -> int:
    Config = _config()
    engine = create_engine(Config.DB_ESTADOS_URL)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                select
                    c.id,
                    c.timestamp,
                    c.fins_ok,
                    c.secciones_status,
                    coalesce(sum(case when s.manual_activo then 1 else 0 end), 0)
                        as manual_activo,
                    coalesce(sum(case when s.automatico_calculado then 1 else 0 end), 0)
                        as automatico_calculado,
                    coalesce(sum(case when s.salida_interna then 1 else 0 end), 0)
                        as salida_interna,
                    coalesce(sum(case when s.salida_wr then 1 else 0 end), 0)
                        as salida_wr
                from ciclo c
                left join seccion_estado s on s.ciclo_id = c.id
                group by c.id, c.timestamp, c.fins_ok, c.secciones_status
                order by c.id desc
                limit :limit
                """
            ),
            {"limit": args.limit},
        ).mappings().all()
        print(
            "id | timestamp | fins_ok | sec_status | manual_activo | "
            "automatico_calculado | salida_interna | salida_wr"
        )
        for row in rows:
            print(
                f"{row['id']} | {row['timestamp']} | {row['fins_ok']} | "
                f"{row['secciones_status']} | {row['manual_activo']} | "
                f"{row['automatico_calculado']} | {row['salida_interna']} | "
                f"{row['salida_wr']}"
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Alumbrado local pipeline checks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("effective-config").set_defaults(func=effective_config)
    subparsers.add_parser("mqtt-broker-host").set_defaults(func=mqtt_broker_host)
    subparsers.add_parser("inspect-config").set_defaults(func=inspect_config)

    db_parser = subparsers.add_parser("db-liveness")
    db_parser.add_argument("max_age_seconds", type=int)
    db_parser.add_argument("max_ingest_age_seconds", type=int)
    db_parser.add_argument("sample_wait_seconds", type=int)
    db_parser.set_defaults(func=db_liveness)

    recent_parser = subparsers.add_parser("recent-cycles")
    recent_parser.add_argument("--limit", type=int, default=30)
    recent_parser.set_defaults(func=recent_cycles)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
