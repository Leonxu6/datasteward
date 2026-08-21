"""Pure helpers for building durable audit-log fields."""
from __future__ import annotations

import json
from collections.abc import Iterable


def safe_json(value) -> str:
    """Serialize tool arguments without letting exotic scalar types break auditing."""
    try:
        return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    except (TypeError, ValueError, RecursionError):
        return json.dumps({"serialization_error": True, "repr": repr(value)[:1000]}, ensure_ascii=False)


def join_labels(values: Iterable | None) -> str:
    """Join optional labels while tolerating scalar types and dropping empty values."""
    if not values:
        return ""
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            result.append(text[:200])
    return ",".join(result)


def elapsed_ms(start_time: float, end_time: float) -> int:
    """Return a nonnegative integer duration even if the wall clock jumps backwards."""
    try:
        delta = (float(end_time) - float(start_time)) * 1000
    except (TypeError, ValueError, OverflowError):
        return 0
    if delta <= 0:
        return 0
    return int(delta)
