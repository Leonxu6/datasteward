"""Detect process-wide threading.stack_size() mutation."""
from __future__ import annotations
import argparse
from pathlib import Path
from scripts.audit_ast_rules import call_name, iter_calls
from scripts.audit_common import print_failures, production_python_files, require_root

def audit_source(source: str) -> list[str]:
    return [f"threading.stack_size() mutates the default thread stack on line {c.lineno}" for c in iter_calls(source) if call_name(c) == "threading.stack_size" and c.args]

def audit(root: Path) -> list[str]:
    root=require_root(root); out=[]
    for rel in production_python_files(root):
        try: src=(root/rel).read_text(encoding="utf-8")
        except (OSError,UnicodeDecodeError): continue
        out.extend(f"{rel}: {x}" for x in audit_source(src))
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("root",nargs="?",default="."); return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__": raise SystemExit(main())
