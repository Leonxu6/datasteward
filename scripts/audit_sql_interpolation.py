"""Detect f-string, percent-formatted, and .format() SQL passed directly to execute methods."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, production_python_files, require_root

def _interpolated(node: ast.AST) -> bool:
    if isinstance(node,ast.JoinedStr): return True
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Mod): return True
    return isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="format"
def audit_source(source: str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError: return []
    out=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in {"execute","executemany"} and n.args and _interpolated(n.args[0]):
            out.append(f"interpolated SQL passed to {n.func.attr}() on line {n.lineno}; use driver parameters or validated identifiers")
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
