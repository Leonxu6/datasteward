"""Detect process-wide sys.excepthook replacement in production modules."""
from __future__ import annotations
import argparse
from pathlib import Path
from scripts.audit_ast_rules import assignment_targets, iter_assignments
from scripts.audit_common import print_failures, production_python_files, require_root

def audit_source(source: str) -> list[str]:
    out=[]
    for node in iter_assignments(source):
        if "sys.excepthook" in assignment_targets(node):
            out.append(f"sys.excepthook replacement mutates process error handling on line {node.lineno}")
    return out

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
