"""Flag pickle and marshal imports in tracked Python source."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files
_UNSAFE={"pickle","marshal"}
def audit_source(s:str)->list[str]:
    try:t=ast.parse(s)
    except SyntaxError:return []
    out=[]
    for n in ast.walk(t):
        if isinstance(n,ast.Import):
            for a in n.names:
                if a.name.split('.',1)[0] in _UNSAFE:out.append(f"unsafe deserialization module {a.name!r} imported on line {n.lineno}")
        elif isinstance(n,ast.ImportFrom) and n.module and n.module.split('.',1)[0] in _UNSAFE:out.append(f"unsafe deserialization module {n.module!r} imported on line {n.lineno}")
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
