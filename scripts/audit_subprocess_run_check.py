"""Detect subprocess.run() calls that do not opt into failure propagation with check=True."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root

def audit_source(source: str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError: return []
    out=[]
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Attribute) or not isinstance(n.func.value,ast.Name) or n.func.value.id!="subprocess" or n.func.attr!="run": continue
        check=next((k.value for k in n.keywords if k.arg=="check"),None)
        if not isinstance(check,ast.Constant) or check.value is not True: out.append(f"subprocess.run() without check=True on line {n.lineno}; handle non-zero exits explicitly")
    return out

def audit(root: Path)->list[str]:
    root=require_root(root); out=[]
    for rel in production_python_files(root):
        try: src=(root/rel).read_text(encoding="utf-8")
        except (OSError,UnicodeDecodeError): continue
        out.extend(f"{rel}: {x}" for x in audit_source(src))
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("root",nargs="?",default="."); return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__": raise SystemExit(main())
