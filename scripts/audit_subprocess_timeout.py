"""Detect subprocess helper calls that can wait forever without a timeout."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files
_HELPERS={'run','call','check_call','check_output'}
def audit_source(source:str)->list[str]:
    try:tree=ast.parse(source)
    except SyntaxError:return []
    out=[]
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Attribute):continue
        if not isinstance(n.func.value,ast.Name) or n.func.value.id!='subprocess' or n.func.attr not in _HELPERS:continue
        if not any(k.arg=='timeout' for k in n.keywords):out.append(f"subprocess.{n.func.attr}() without timeout on line {n.lineno}")
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
