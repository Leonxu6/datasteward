"""Detect subprocess.run() calls that omit an explicit non-zero exit policy."""
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
    out: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr == "run"
        ):
            continue
        if not any(keyword.arg == "check" for keyword in node.keywords):
            out.append(
                f"subprocess.run() without explicit check policy on line {node.lineno}; "
                "use check=True or check=False with explicit return-code handling"
            )
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
