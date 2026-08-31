"""Pure helpers for building durable audit-log fields."""
from __future__ import annotations

import json
import math
from collections.abc import Iterable

_MAX_LABELS = 100
_MAX_JOINED_LABEL_CHARS = 10_000
_MAX_JSON_CHARS = 100_000
_BIDI_CONTROLS = {
    "\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
}


def _safe_repr(value: object, *, limit: int = 1000) -> str:
    try:
        rendered = repr(value)
    except Exception:  # noqa: BLE001
        rendered = f"<{value.__class__.__name__}>"
    return rendered[:limit]


def _sanitize_text(value: str) -> str:
    cleaned = "".join(
        ch if ord(ch) >= 32 and ord(ch) != 127 and ch not in _BIDI_CONTROLS else " "
        for ch in value
    )
    return " ".join(cleaned.split()).strip()


def _safe_json_default(value: object) -> str:
    """Render unknown JSON values without trusting user-defined ``__str__`` methods."""
    try:
        return _sanitize_text(str(value))
    except Exception:  # noqa: BLE001
        raise TypeError("value could not be converted to text")


def _json_fallback(value: object, *, reason: str | None = None) -> str:
    payload = {"serialization_error": True, "repr": _safe_repr(value)}
    if reason:
        payload["reason"] = reason
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True)


def safe_json(value) -> str:
    """Serialize tool arguments as bounded standards-compliant JSON without breaking auditing."""
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            default=_safe_json_default,
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError, OverflowError):
        return _json_fallback(value)
    if len(rendered) > _MAX_JSON_CHARS:
        return _json_fallback(value, reason="serialized value exceeds audit limit")
    return rendered


def _safe_label_text(value: object) -> str:
    try:
        rendered = str(value)
    except Exception:  # noqa: BLE001
        rendered = value.__class__.__name__
    return _sanitize_text(rendered)


def join_labels(values: Iterable | None) -> str:
    """Join optional labels without materializing an unbounded external iterable."""
    if values is None:
        return ""
    if isinstance(values, str):
        iterator = iter([values])
    elif isinstance(values, (bytes, bytearray, dict)):
        raise ValueError("labels must be text values, not bytes or mappings")
    else:
        try:
            iterator = iter(values)
        except TypeError as exc:
            raise ValueError("labels must be iterable") from exc
    result: list[str] = []
    seen: set[str] = set()
    total_chars = 0
    for value in iterator:
        if len(result) >= _MAX_LABELS:
            raise ValueError(f"labels must contain at most {_MAX_LABELS} values")
        text = _safe_label_text(value)[:200].rstrip()
        if text and text not in seen:
            additional = len(text) + (1 if result else 0)
            if total_chars + additional > _MAX_JOINED_LABEL_CHARS:
                raise ValueError(f"joined labels must be at most {_MAX_JOINED_LABEL_CHARS} characters")
            result.append(text)
            seen.add(text)
            total_chars += additional
    return ",".join(result)


def elapsed_ms(start_time: float, end_time: float) -> int:
    """Return a finite nonnegative integer duration even for malformed clock values."""
    if isinstance(start_time, bool) or isinstance(end_time, bool):
        return 0
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
