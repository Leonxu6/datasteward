"""Detect machine-specific absolute user-home literals in tracked Python code."""
from __future__ import annotations
import argparse,ast,re
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files
_WINDOWS_USER=re.compile(r"^[A-Za-z]:[\\/]Users[\\/]")
def audit_source(source:str)->list[str]:
    try:tree=ast.parse(source)
    except SyntaxError:return []
    out=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Constant) and isinstance(n.value,str) and (n.value.startswith(('/Users/','/home/')) or _WINDOWS_USER.match(n.value)):out.append(f"machine-specific user path on line {n.lineno}")
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
