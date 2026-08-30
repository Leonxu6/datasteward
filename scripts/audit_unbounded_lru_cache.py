"""Detect functools.lru_cache(maxsize=None) in long-lived runtime modules."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root

def audit_source(source:str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError: return []
    out=[]
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call): continue
        f=n.func
        if not (isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id=="functools" and f.attr=="lru_cache"): continue
        unbounded=(n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value is None) or any(k.arg=="maxsize" and isinstance(k.value,ast.Constant) and k.value.value is None for k in n.keywords)
        if unbounded: out.append(f"unbounded functools.lru_cache() on line {n.lineno}")
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
