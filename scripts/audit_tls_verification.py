"""Detect explicit verify=False HTTP client calls."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files

def audit_source(s:str)->list[str]:
    try:t=ast.parse(s)
    except SyntaxError:return []
    out=[]
    for n in ast.walk(t):
        if isinstance(n,ast.Call) and any(k.arg=='verify' and isinstance(k.value,ast.Constant) and k.value.value is False for k in n.keywords):out.append(f"TLS verification disabled with verify=False on line {n.lineno}")
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
