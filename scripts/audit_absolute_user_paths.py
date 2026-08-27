"""Detect machine-specific absolute user-home literals in runtime Python code."""
from __future__ import annotations
import argparse, ast, re
from pathlib import Path
from scripts.audit_common import print_failures, require_root, tracked_files
_WINDOWS_USER = re.compile(r"^[A-Za-z]:[\\/]Users[\\/]")
_IGNORED_TOP_LEVEL = {"scripts", "tests"}

def audit_source(source: str) -> list[str]:
    try: tree = ast.parse(source)
    except SyntaxError: return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and (node.value.startswith(("/Users/", "/home/")) or _WINDOWS_USER.match(node.value)):
            out.append(f"machine-specific user path on line {node.lineno}")
    return out

def audit(root: Path) -> list[str]:
    root = require_root(root); out = []
    for rel in tracked_files(root):
        if rel.suffix != ".py" or (rel.parts and rel.parts[0] in _IGNORED_TOP_LEVEL): continue
        try: source = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError): continue
        out.extend(f"{rel}: {item}" for item in audit_source(source))
    return out

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("root", nargs="?", default=".")
    return print_failures(audit(Path(parser.parse_args(argv).root)))
if __name__ == "__main__": raise SystemExit(main())
