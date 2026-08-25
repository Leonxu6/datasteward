"""Detect tracked path collisions on case-insensitive developer filesystems."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.audit_common import print_failures, require_root, tracked_files


def audit_paths(paths: list[Path]) -> list[str]:
    seen: dict[str, Path] = {}; failures: list[str] = []
    for path in paths:
        key = path.as_posix().casefold(); previous = seen.get(key)
        if previous is not None and previous != path:
            failures.append(f"case-insensitive path collision: {previous} <-> {path}")
        else: seen[key] = path
    return failures


def audit(root: Path) -> list[str]:
    require_root(root); return audit_paths(tracked_files(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv); return print_failures(audit(Path(args.root)))


if __name__ == "__main__": raise SystemExit(main())
