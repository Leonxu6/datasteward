"""Detect list/dict/set literals used as mutable function defaults."""
from __future__ import annotations
import argparse, ast
from pathlib import Path
from scripts.audit_common import print_failures, require_root, tracked_files
_MUTABLE=(ast.List,ast.Dict,ast.Set)
def audit_source(source:str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError: return []
    out=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        defaults=[*node.args.defaults,*(v for v in node.args.kw_defaults if v is not None)]
        if any(isinstance(d,_MUTABLE) for d in defaults): out.append(f"mutable default in {node.name} on line {node.lineno}")
    return out
def audit(root:Path)->list[str]:
    root=require_root(root); out=[]
    for rel in tracked_files(root):
        if rel.suffix!='.py': continue
        try: source=(root/rel).read_text(encoding='utf-8')
        except (OSError,UnicodeDecodeError): continue
        out.extend(f"{rel}: {item}" for item in audit_source(source))
    return out
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('root',nargs='?',default='.'); return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=='__main__': raise SystemExit(main())
