"""Detect text-mode open() calls that rely on the platform default encoding."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root


def audit_source(source: str) -> list[str]:
    try: tree = ast.parse(source)
    except SyntaxError: return []
    failures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "open": continue
        mode = "r"
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str): mode = node.args[1].value
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str): mode = kw.value.value
        if "b" not in mode and not any(kw.arg == "encoding" for kw in node.keywords):
            failures.append(f"text open() without explicit encoding on line {node.lineno}")
    return failures


def audit(root: Path) -> list[str]:
    root = require_root(root); failures: list[str] = []
    for rel in production_python_files(root):
        try: source = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError): continue
        failures.extend(f"{rel}: {item}" for item in audit_source(source))
    return failures


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("root", nargs="?", default=".")
    return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__ == "__main__": raise SystemExit(main())
