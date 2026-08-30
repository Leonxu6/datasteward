"""Detect obviously destructive literal SQL that deserves explicit review."""
from __future__ import annotations
import argparse, ast, re
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root
_DANGEROUS=re.compile(r"^\s*(drop\s+(table|database|schema)|truncate\s+table|delete\s+from\s+\S+\s*;?\s*$)",re.I)
def audit_source(source:str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError: return []
    out=[]
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Attribute) or n.func.attr not in {"execute","executemany"} or not n.args: continue
        sql=n.args[0]
        if isinstance(sql,ast.Constant) and isinstance(sql.value,str) and _DANGEROUS.match(sql.value): out.append(f"destructive literal SQL on line {n.lineno}")
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
