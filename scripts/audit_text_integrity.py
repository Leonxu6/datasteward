"""Audit tracked text files for portable UTF-8 encoding and final newlines."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.audit_common import TEXT_SUFFIXES, print_failures, require_root, tracked_files


def audit_paths(root: Path, paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for rel in paths:
        if rel.suffix.lower() not in TEXT_SUFFIXES:
            continue
        path = root / rel
        try:
            data = path.read_bytes()
        except OSError as exc:
            failures.append(f"{rel}: unreadable ({exc})")
            continue
        if data.startswith(b"\xef\xbb\xbf"):
            failures.append(f"{rel}: UTF-8 BOM is not allowed")
        if b"\x00" in data:
            failures.append(f"{rel}: contains NUL bytes")
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            failures.append(f"{rel}: is not valid UTF-8")
        if data and not data.endswith(b"\n"):
            failures.append(f"{rel}: missing final newline")
    return failures


def audit(root: Path) -> list[str]:
    root = require_root(root)
    return audit_paths(root, tracked_files(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    return print_failures(audit(Path(args.root)))


if __name__ == "__main__":
    raise SystemExit(main())
