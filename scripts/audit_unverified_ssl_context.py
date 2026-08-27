"""Detect creation of SSL contexts that deliberately disable certificate verification."""
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
        f"ssl._create_unverified_context() call on line {node.lineno}"
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "ssl"
            and node.func.attr == "_create_unverified_context"
        )
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
