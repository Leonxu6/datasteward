"""Detect torch.load(..., weights_only=False) calls that opt into pickle-backed object loading."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_ast_rules import call_name, iter_calls
from scripts.audit_common import print_failures, production_python_files, require_root

def audit_source(source: str) -> list[str]:
    out=[]
    for c in iter_calls(source):
        if call_name(c)!="torch.load": continue
        for kw in c.keywords:
            if kw.arg=="weights_only" and isinstance(kw.value,ast.Constant) and kw.value.value is False:
                out.append(f"torch.load disables weights-only loading on line {c.lineno}")
    return out

def audit(root: Path) -> list[str]:
    root=require_root(root); out=[]
    for rel in production_python_files(root):
        try: src=(root/rel).read_text(encoding="utf-8")
        except (OSError,UnicodeError): continue
        out.extend(f"{rel}: {item}" for item in audit_source(src))
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("root",nargs="?",default="."); return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__": raise SystemExit(main())