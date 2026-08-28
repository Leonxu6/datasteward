"""Detect process-wide os.environ mutation in production modules."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root

def _is_environ(node: ast.AST) -> bool:
    return isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id=="os" and node.attr=="environ"
def audit_source(source: str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError: return []
    out=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
            targets = n.targets if isinstance(n,ast.Assign) else [n.target]
            if any(isinstance(t,ast.Subscript) and _is_environ(t.value) for t in targets): out.append(f"os.environ assignment mutates process state on line {n.lineno}")
        elif isinstance(n,ast.Delete) and any(isinstance(t,ast.Subscript) and _is_environ(t.value) for t in n.targets): out.append(f"os.environ deletion mutates process state on line {n.lineno}")
        elif isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and _is_environ(n.func.value) and n.func.attr in {"clear","pop","popitem","setdefault","update"}: out.append(f"os.environ.{n.func.attr}() mutates process state on line {n.lineno}")
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
