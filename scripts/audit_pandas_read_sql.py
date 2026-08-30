"""Detect pandas.read_sql*() calls without chunksize in service code."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root
_TARGETS={"read_sql","read_sql_query","read_sql_table"}
def audit_source(source:str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError: return []
    out=[]
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f=n.func
        if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id in {"pd","pandas"} and f.attr in _TARGETS and not any(k.arg=="chunksize" for k in n.keywords): out.append(f"pandas.{f.attr}() without chunksize on line {n.lineno}")
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
