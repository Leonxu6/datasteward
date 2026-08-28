"""Detect random.seed() calls that mutate module-global pseudo-random state."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root

def audit_source(source: str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError: return []
    return [f"random.seed() mutates module-global RNG state on line {n.lineno}" for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=="random" and n.func.attr=="seed"]
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
