"""Pure helpers for building durable audit-log fields."""
from __future__ import annotations

import json
import math
from collections.abc import Iterable


def _safe_repr(value: object, *, limit: int = 1000) -> str:
    try:
        rendered = repr(value)
    except Exception:  # noqa: BLE001
        rendered = f"<{value.__class__.__name__}>"
    return rendered[:limit]


def _safe_json_default(value: object) -> str:
    """Render unknown JSON values without trusting user-defined ``__str__`` methods."""
    try:
        return str(value)
    except Exception:  # noqa: BLE001
        raise TypeError("value could not be converted to text")


def safe_json(value) -> str:
    """Serialize tool arguments as standards-compliant JSON without breaking auditing."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=_safe_json_default,
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError, OverflowError):
        return json.dumps(
            {"serialization_error": True, "repr": _safe_repr(value)},
            ensure_ascii=False,
            allow_nan=False,
        )


def join_labels(values: Iterable | None) -> str:
    """Join optional labels, treating a scalar string as one label rather than characters."""
    if values is None:
        return ""
    if isinstance(values, str):
        values = [values]
    elif isinstance(values, (bytes, bytearray, dict)):
        raise ValueError("labels must be text values, not bytes or mappings")
    else:
        try:
            values = list(values)
        except TypeError as exc:
            raise ValueError("labels must be iterable") from exc
    result: list[str] = []
    for value in values:
        try:
            text = str(value).strip()
        except Exception:  # noqa: BLE001
            text = value.__class__.__name__
        if text:
            result.append(text[:200])
    return ",".join(result)


def elapsed_ms(start_time: float, end_time: float) -> int:
    """Return a finite nonnegative integer duration even for malformed clock values."""
    try:
        start = float(start_time)
        end = float(end_time)
        if not math.isfinite(start) or not math.isfinite(end):
            return 0
        delta = (end - start) * 1000
        if not math.isfinite(delta) or delta <= 0:
            return 0
        return int(delta)
    except (TypeError, ValueError, OverflowError):
        return 0
