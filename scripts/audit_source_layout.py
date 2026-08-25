"""Validate the src-layout package boundary used by setuptools."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.audit_common import print_failures, require_root, tracked_files


def audit_paths(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        if not path.parts or path.parts[0] != "src" or path.suffix != ".py":
            continue
        if len(path.parts) < 2 or path.parts[1] != "dm":
            failures.append(f"{path}: Python source under src/ must belong to the dm package")
    if Path("src/dm/__init__.py") not in paths:
        failures.append("src/dm/__init__.py: package initializer is missing")
    return failures


def audit(root: Path) -> list[str]:
    require_root(root); return audit_paths(tracked_files(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv); return print_failures(audit(Path(args.root)))


if __name__ == "__main__": raise SystemExit(main())
