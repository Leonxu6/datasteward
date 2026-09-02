"""Detect SQLite extension-loading APIs that execute native code."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_ast_rules import call_name, iter_calls
from scripts.audit_common import print_failures, production_python_files, require_root

def audit_source(source: str) -> list[str]:
    out=[]
    for c in iter_calls(source):
        name=call_name(c) or ""
        if name.endswith(".load_extension"):
            out.append(f"SQLite load_extension executes native code on line {c.lineno}")
        elif name.endswith(".enable_load_extension") and c.args and isinstance(c.args[0],ast.Constant) and c.args[0].value is True:
            out.append(f"SQLite extension loading enabled on line {c.lineno}")
    return out

def audit(root: Path) -> list[str]:
    root=require_root(root); out=[]
    for rel in production_python_files(root):
        try: src=(root/rel).read_text(encoding="utf-8")
        except (OSError, UnicodeError): continue
        out.extend(f"{rel}: {x}" for x in audit_source(src))
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("root",nargs="?",default=".")
    return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__": raise SystemExit(main())
