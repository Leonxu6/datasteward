"""Detect common httpx request/client construction without an explicit timeout policy."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root
_TARGETS={"get","post","put","patch","delete","request","Client","AsyncClient"}
def audit_source(source:str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError: return []
    out=[]
    for n in ast.walk(tree):
        f=n.func
        if isinstance(n,ast.Call) and isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id=="httpx" and f.attr in _TARGETS and not any(k.arg=="timeout" for k in n.keywords): out.append(f"httpx.{f.attr}() without explicit timeout on line {n.lineno}")
    return out
def audit(root:Path)->list[str]:
    root=require_root(root); out=[]
    for rel in production_python_files(root):
        try: src=(root/rel).read_text(encoding="utf-8")
        except (OSError,UnicodeDecodeError): continue
        out.extend(f"{rel}: {x}" for x in audit_source(src))
    return out
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("root",nargs="?",default="."); return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__": raise SystemExit(main())
