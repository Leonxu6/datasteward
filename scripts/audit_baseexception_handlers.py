"""Detect handlers that catch ``BaseException`` and swallow process control signals."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

from scripts.audit_common import print_failures, production_python_files, require_root


def _catches_base_exception(node: ast.expr | None) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "BaseException"
    if isinstance(node, ast.Tuple):
        return any(_catches_base_exception(item) for item in node.elts)
    return False


def audit_source(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [
        f"BaseException handler on line {node.lineno}; catch a narrower exception"
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler) and _catches_base_exception(node.type)
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
