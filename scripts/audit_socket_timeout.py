"""Detect socket.create_connection() calls without an explicit timeout."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

from scripts.audit_common import print_failures, production_python_files, require_root


def _is_create_connection(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "socket"
        and node.func.attr == "create_connection"
    )


def audit_source(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    failures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_create_connection(node):
            continue
        has_timeout = len(node.args) >= 2 or any(keyword.arg == "timeout" for keyword in node.keywords)
        if not has_timeout:
            failures.append(f"socket.create_connection() without timeout on line {node.lineno}")
    return failures


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
