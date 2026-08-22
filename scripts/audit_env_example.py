#!/usr/bin/env python3
"""Validate .env.example syntax without loading values into the environment."""
from __future__ import annotations

from pathlib import Path
import re

_KEY = re.compile(r"^[A-Z][A-Z0-9_]*$")


def audit_env_file(path: Path) -> list[tuple[int, str]]:
    issues: list[tuple[int, str]] = []
    seen: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in raw:
            issues.append((number, "setting must contain '='"))
            continue
        key, value = raw.split("=", 1)
        if key != key.strip() or not _KEY.fullmatch(key):
            issues.append((number, "invalid environment variable name"))
            continue
        if key in seen:
            issues.append((number, f"duplicate setting: {key}"))
        seen.add(key)
        if value != value.strip():
            issues.append((number, f"{key} value has surrounding whitespace"))
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            issues.append((number, f"{key} value contains control characters"))
    return issues


def main() -> int:
    path = Path(__file__).resolve().parents[1] / ".env.example"
    issues = audit_env_file(path)
    for line, message in issues:
        print(f"{path}:{line}: {message}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
