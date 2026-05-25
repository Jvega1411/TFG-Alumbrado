import importlib.util
from pathlib import Path


def _load_pipeline_checks():
    path = Path(__file__).parents[1] / "scripts" / "node-config" / "pipeline_checks.py"
    spec = importlib.util.spec_from_file_location("pipeline_checks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_db_url_hides_password():
    checks = _load_pipeline_checks()

    safe = checks._safe_db_url("mssql+pyodbc://user:secret@example/db")

    assert "secret" not in safe
    assert "***" in safe


def test_parser_accepts_recent_cycles_limit():
    checks = _load_pipeline_checks()

    args = checks.build_parser().parse_args(["recent-cycles", "--limit", "5"])

    assert args.limit == 5
