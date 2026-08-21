"""Safe JSONL persistence helpers for audit/task/eval logs."""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

_LOG_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def normalize_log_name(name) -> str:
    """Reject path traversal and ambiguous log file names."""
    if not isinstance(name, str) or not _LOG_NAME.fullmatch(name):
        raise ValueError("log name must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    return name


def log_path(log_dir: Path, name) -> Path:
    return log_dir / f"{normalize_log_name(name)}.jsonl"


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def encode_record(record: dict) -> bytes:
    if not isinstance(record, dict):
        raise TypeError("record must be a dict")
    line = json.dumps(record, ensure_ascii=False, default=_json_default, separators=(",", ":"))
    return (line + "\n").encode("utf-8")


def append_jsonl(log_dir: Path, name, record: dict) -> None:
    """Append one complete UTF-8 JSON line using an O_APPEND file descriptor."""
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_path(log_dir, name)
    payload = encode_record(record)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
    try:
        written = os.write(fd, payload)
        if written != len(payload):
            raise OSError(f"short JSONL append: wrote {written}/{len(payload)} bytes")
    finally:
        os.close(fd)


def read_jsonl(log_dir: Path, name) -> list[dict]:
    """Read valid JSON-object lines while tolerating interrupted/corrupt records."""
    path = log_path(log_dir, name)
    if not path.exists():
        return []
    output: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                output.append(value)
    return output
