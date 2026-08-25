"""Compile tracked Python sources without importing runtime dependencies."""
from __future__ import annotations

import argparse
import py_compile
from pathlib import Path

from scripts.audit_common import print_failures, require_root, tracked_files


def audit_paths(root: Path, paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for rel in paths:
        if rel.suffix != ".py":
            continue
        try:
            py_compile.compile(str(root / rel), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"{rel}: {' '.join(str(exc).split())[:500]}")
        except OSError as exc:
            failures.append(f"{rel}: unreadable ({exc})")
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
