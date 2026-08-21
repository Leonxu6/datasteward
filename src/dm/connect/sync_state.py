"""Durable helpers for connector watermarks and incremental sync state."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


def load_json_mapping(path: Path) -> dict:
    """Load a JSON object, returning an empty mapping for missing/corrupt/non-object files."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def atomic_write_json(path: Path, value: dict) -> None:
    """Atomically replace a JSON state file so crashes cannot leave partial content."""
    if not isinstance(value, dict):
        raise TypeError("value must be a dict")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=1, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def max_non_null(values: Iterable):
    """Return the maximum non-null cursor value, or ``None`` when all values are null."""
    candidates = [value for value in values if value is not None]
    return max(candidates) if candidates else None


def serialize_watermark(value):
    """Keep JSON-friendly scalars intact while serializing date/time cursor values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def validate_requested_names(requested: Iterable[str] | None, available: Iterable[str]) -> list[str] | None:
    """Validate explicitly requested table names instead of silently ignoring typos."""
    if requested is None:
        return None
    allowed = set(available)
    result: list[str] = []
    seen: set[str] = set()
    for name in requested:
        if not isinstance(name, str) or not name or name != name.strip():
            raise ValueError(f"invalid table name: {name!r}")
        if name not in allowed:
            raise ValueError(f"unknown table: {name}")
        if name not in seen:
            result.append(name)
            seen.add(name)
    return result
