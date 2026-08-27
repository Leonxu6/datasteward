"""Detect ``os.system`` and ``os.popen`` command execution in tracked Python."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files
def audit_source(source:str)->list[str]:
    try:tree=ast.parse(source)
    except SyntaxError:return []
    out=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='os' and n.func.attr in {'system','popen'}:out.append(f"os.{n.func.attr}() command execution on line {n.lineno}")
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
