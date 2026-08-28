"""Detect datetime.now() values that remain naive beyond immediate local formatting."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

from scripts.audit_common import print_failures, production_python_files, require_root


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_immediate_strftime(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow datetime.now().strftime(...): no naive datetime object escapes the expression."""
    parent = parents.get(call)
    return (
        isinstance(parent, ast.Attribute)
        and parent.value is call
        and parent.attr == "strftime"
        and isinstance(parents.get(parent), ast.Call)
        and parents[parent].func is parent
    )


def audit_source(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    parents = _parent_map(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "now"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "datetime"
        ):
            continue
        if node.args or any(keyword.arg in {"tz", "timezone"} for keyword in node.keywords):
            continue
        if _is_immediate_strftime(node, parents):
            continue
        out.append(f"datetime.now() without timezone on line {node.lineno}")
    return out


def audit(root: Path) -> list[str]:
    root = require_root(root)
    out: list[str] = []
    for rel in production_python_files(root):
        try:
            src = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out.extend(f"{rel}: {finding}" for finding in audit_source(src))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    return print_failures(audit(Path(parser.parse_args(argv).root)))


if __name__ == "__main__":
    raise SystemExit(main())
