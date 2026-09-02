"""Detect concurrent.futures.as_completed() calls without timeout bounds."""
from __future__ import annotations
import argparse
from pathlib import Path
from scripts.audit_ast_rules import call_name, has_keyword, iter_calls
from scripts.audit_common import print_failures, production_python_files, require_root

def audit_source(source: str) -> list[str]:
    out=[]
    for call in iter_calls(source):
        if call_name(call) in {"concurrent.futures.as_completed", "futures.as_completed"} and len(call.args) < 2 and not has_keyword(call, "timeout"):
            out.append(f"as_completed without timeout on line {call.lineno}")
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