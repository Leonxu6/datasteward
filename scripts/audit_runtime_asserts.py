"""Detect runtime ``assert`` statements that disappear under optimized Python."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

from scripts.audit_common import print_failures, production_python_files, require_root


def audit_source(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [
        f"runtime assert on line {node.lineno}; use explicit validation instead"
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert)
    ]


def audit(root: Path) -> list[str]:
    root = require_root(root)
    failures: list[str] = []
    for rel in production_python_files(root):
        try:
            source = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        failures.extend(f"{rel}: {item}" for item in audit_source(source))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    return print_failures(audit(Path(parser.parse_args(argv).root)))


if __name__ == "__main__":
    raise SystemExit(main())
