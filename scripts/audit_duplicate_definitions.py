"""Detect duplicate function, class, and method definitions in the same scope."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files

def _property_mutator(node):
    if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):return False
    for decorator in node.decorator_list:
        if isinstance(decorator,ast.Attribute) and decorator.attr in {'setter','deleter'}:
            if isinstance(decorator.value,ast.Name) and decorator.value.id==node.name:return True
    return False

def _dupes(body,scope):
    seen=set();out=[]
    for n in body:
        if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):continue
        if n.name in seen and not _property_mutator(n):out.append(f"duplicate definition {scope}{n.name} on line {n.lineno}")
        seen.add(n.name)
    return out
def audit_source(source:str)->list[str]:
    try:tree=ast.parse(source)
    except SyntaxError:return []
    out=_dupes(tree.body,'')
    for n in ast.walk(tree):
        if isinstance(n,ast.ClassDef):out.extend(_dupes(n.body,f'{n.name}.'))
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
