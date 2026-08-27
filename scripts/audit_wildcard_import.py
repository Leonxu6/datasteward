"""Detect wildcard imports that obscure runtime dependencies."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files
def audit_source(source:str)->list[str]:
    try: tree=ast.parse(source)
    except SyntaxError:return []
    out=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom) and any(a.name=='*' for a in node.names):
            out.append(f"wildcard import from {node.module or 'relative module'} on line {node.lineno}")
    return out
def audit(root:Path)->list[str]:
    root=require_root(root);out=[]
    for rel in tracked_files(root):
        if rel.suffix!='.py':continue
        try:source=(root/rel).read_text(encoding='utf-8')
        except (OSError,UnicodeDecodeError):continue
        out.extend(f"{rel}: {x}" for x in audit_source(source))
    return out
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',nargs='?',default='.');return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=='__main__':raise SystemExit(main())
