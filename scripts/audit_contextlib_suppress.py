"""Detect broad contextlib.suppress() calls that can hide operational failures."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root


def audit_source(source: str) -> list[str]:
    try: tree = ast.parse(source)
    except SyntaxError: return []
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call): continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "contextlib" and func.attr == "suppress"):
            continue
        broad = {"Exception", "BaseException"}
        if any(isinstance(arg, ast.Name) and arg.id in broad for arg in node.args):
            out.append(f"broad contextlib.suppress() on line {node.lineno}")
    return out


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
