"""Safe JSONL persistence helpers for audit/task/eval logs."""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

_LOG_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_MAX_LINE_BYTES = 1024 * 1024


def _log_dir(value) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise ValueError("log_dir must be a filesystem path")
    try:
        return Path(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("log_dir must be a valid filesystem path") from exc


def normalize_log_name(name) -> str:
    """Reject path traversal and ambiguous log file names."""
    if not isinstance(name, str) or not _LOG_NAME.fullmatch(name):
        raise ValueError("log name must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    return name


def log_path(log_dir: Path, name) -> Path:
    return _log_dir(log_dir) / f"{normalize_log_name(name)}.jsonl"


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def encode_record(record: dict) -> bytes:
    if not isinstance(record, dict):
        raise TypeError("record must be a dict")
    line = json.dumps(
        record,
        ensure_ascii=False,
        default=_json_default,
        separators=(",", ":"),
        allow_nan=False,
    )
    payload = (line + "\n").encode("utf-8")
    if len(payload) > _MAX_LINE_BYTES:
        raise ValueError(f"JSONL record exceeds {_MAX_LINE_BYTES} bytes")
    return payload


def append_jsonl(log_dir: Path, name, record: dict) -> None:
    """Append and fsync one complete bounded UTF-8 JSON line."""
    directory = _log_dir(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = log_path(directory, name)
    payload = encode_record(record)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise OSError(f"short JSONL append stalled after {offset}/{len(payload)} bytes")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)


def read_jsonl(log_dir: Path, name) -> list[dict]:
    """Read bounded valid JSON-object lines while skipping corrupt/oversized records."""
    path = log_path(log_dir, name)
    if not path.exists():
        return []
    output: list[dict] = []
    with path.open("rb") as handle:
        while True:
            line = handle.readline(_MAX_LINE_BYTES + 1)
            if not line:
                break
            if len(line) > _MAX_LINE_BYTES:
                if not line.endswith(b"\n"):
                    while line and not line.endswith(b"\n"):
                        line = handle.readline(_MAX_LINE_BYTES + 1)
                continue
            try:
                text = line.decode("utf-8").strip()
            except UnicodeDecodeError:
                continue
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                output.append(value)
    return output
