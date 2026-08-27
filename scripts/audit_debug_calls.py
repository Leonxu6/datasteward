"""Detect tracked Python code that leaves interactive debugger entry points enabled."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files
def audit_source(source:str)->list[str]:
    try:tree=ast.parse(source)
    except SyntaxError:return []
    out=[]
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call):continue
        if isinstance(n.func,ast.Name) and n.func.id=='breakpoint':out.append(f"breakpoint() on line {n.lineno}")
        elif isinstance(n.func,ast.Attribute) and n.func.attr=='set_trace' and isinstance(n.func.value,ast.Name) and n.func.value.id in {'pdb','ipdb'}:out.append(f"{n.func.value.id}.set_trace() on line {n.lineno}")
    return out
def audit(root:Path)->list[str]:
    root=require_root(root);out=[]
    for rel in tracked_files(root):
        if rel.suffix!='.py':continue
        try:s=(root/rel).read_text(encoding='utf-8')
        except (OSError,UnicodeDecodeError):continue
        out.extend(f"{rel}: {x}" for x in audit_source(s))
    return out
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',nargs='?',default='.');return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=='__main__':raise SystemExit(main())
