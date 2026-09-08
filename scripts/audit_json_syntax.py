"""Validate tracked JSON files without importing application code."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.audit_common import print_failures, require_root, tracked_files


def _reject_nonstandard_constant(value: str) -> None:
    raise json.JSONDecodeError("nonstandard JSON constant", value, 0)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise json.JSONDecodeError("duplicate JSON object key", key, 0)
        result[key] = value
    return result


def audit_file(path: Path) -> list[str]:
    try:
        json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonstandard_constant,
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"invalid JSON: {exc}"]
    return []


def audit(root: Path) -> list[str]:
    root = require_root(root)
    failures: list[str] = []
    for rel in tracked_files(root):
        if rel.suffix.lower() == ".json":
            failures.extend(f"{rel}: {item}" for item in audit_file(root / rel))
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    return print_failures(audit(Path(parser.parse_args(argv).root)))


if __name__ == "__main__":
    raise SystemExit(main())
