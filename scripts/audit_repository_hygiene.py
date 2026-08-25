"""Reject tracked runtime, cache, and private artifacts."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.audit_common import print_failures, require_root, tracked_files

_FORBIDDEN_NAMES = {".DS_Store", "Thumbs.db", ".env", "warehouse.duckdb", "role_map.yaml", "audit-report.md"}
_FORBIDDEN_PARTS = {"__pycache__", ".pytest_cache", ".venv", "venv", "env", "target", "dbt_packages"}
_FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".duckdb", ".wal"}


def audit_paths(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for rel in paths:
        if rel.name in _FORBIDDEN_NAMES:
            failures.append(f"{rel}: runtime/private artifact is tracked")
        elif any(part in _FORBIDDEN_PARTS for part in rel.parts):
            failures.append(f"{rel}: generated directory content is tracked")
        elif rel.suffix.lower() in _FORBIDDEN_SUFFIXES:
            failures.append(f"{rel}: generated database/bytecode artifact is tracked")
    return failures


def audit(root: Path) -> list[str]:
    require_root(root)
    return audit_paths(tracked_files(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    return print_failures(audit(Path(args.root)))


if __name__ == "__main__":
    raise SystemExit(main())
