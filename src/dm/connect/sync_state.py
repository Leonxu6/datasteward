"""Durable helpers for connector watermarks and incremental sync state."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


def _path(value, *, field: str) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise ValueError(f"{field} must be a filesystem path")
    try:
        path = Path(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a valid filesystem path") from exc
    if not path.name:
        raise ValueError(f"{field} must name a file")
    return path


def _table_name(value, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"invalid {field}: {value!r}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"invalid {field}: control characters are not allowed")
    return value


def load_json_mapping(path: Path) -> dict:
    """Load a JSON object, returning an empty mapping for missing/corrupt/non-object files."""
    path = _path(path, field="state path")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def atomic_write_json(path: Path, value: dict) -> None:
    """Atomically replace a JSON state file so crashes cannot leave partial content."""
    path = _path(path, field="state path")
    if not isinstance(value, dict):
        raise TypeError("value must be a dict")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=1, default=str, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def max_non_null(values: Iterable):
    """Return the maximum non-null cursor value with a stable error for mixed domains."""
    if values is None or isinstance(values, (str, bytes, bytearray, dict)):
        raise ValueError("watermark values must be a non-string iterable")
    try:
        candidates = [value for value in values if value is not None]
    except TypeError as exc:
        raise ValueError("watermark values must be iterable") from exc
    if not candidates:
        return None
    try:
        return max(candidates)
    except TypeError as exc:
        raise ValueError("watermark values must be mutually comparable") from exc


def serialize_watermark(value):
    """Keep JSON-friendly scalars intact while serializing date/time cursor values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def validate_requested_names(requested: Iterable[str] | None, available: Iterable[str]) -> list[str] | None:
    """Validate explicitly requested table names instead of silently ignoring typos."""
    if requested is None:
        return None
    if isinstance(requested, (str, bytes, bytearray, dict)):
        raise ValueError("requested table names must be a non-string iterable")
    if available is None or isinstance(available, (str, bytes, bytearray, dict)):
        raise ValueError("available table names must be a non-string iterable")
    try:
        available_values = list(available)
    except TypeError as exc:
        raise ValueError("available table names must be iterable") from exc
    allowed: set[str] = set()
    for value in available_values:
        name = _table_name(value, field="available table name")
        if name in allowed:
            raise ValueError(f"duplicate available table name: {name}")
        allowed.add(name)

    result: list[str] = []
    seen: set[str] = set()
    try:
        iterator = iter(requested)
    except TypeError as exc:
        raise ValueError("requested table names must be iterable") from exc
    for value in iterator:
        name = _table_name(value, field="table name")
        if name not in allowed:
            raise ValueError(f"unknown table: {name}")
        if name not in seen:
            result.append(name)
            seen.add(name)
    return result
