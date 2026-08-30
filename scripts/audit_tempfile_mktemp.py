"""Detect tempfile.mktemp(), which creates race-prone temporary path names."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root


def audit_source(source: str) -> list[str]:
    try: tree = ast.parse(source)
    except SyntaxError: return []
    return [
        f"tempfile.mktemp() on line {node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "tempfile"
        and node.func.attr == "mktemp"
    ]


def audit(root: Path) -> list[str]:
    root = require_root(root); out: list[str] = []
    for rel in production_python_files(root):
        try: src = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError): continue
        out.extend(f"{rel}: {item}" for item in audit_source(src))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("root", nargs="?", default=".")
    return print_failures(audit(Path(p.parse_args(argv).root)))

if __name__ == "__main__": raise SystemExit(main())
