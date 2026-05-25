"""Helpers for JSON values stored in text database columns."""

from __future__ import annotations

import json
from typing import Any


def dump_json_column(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"))


def load_json_column(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return value
