"""Detect tracked paths that collide after Unicode NFC normalization."""
from __future__ import annotations
import argparse,unicodedata
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files

def audit_paths(paths:list[Path])->list[str]:
    seen={};out=[]
    for path in paths:
        key=unicodedata.normalize('NFC',path.as_posix())
        previous=seen.get(key)
        if previous is not None and previous!=path:out.append(f'Unicode-normalized path collision: {previous} <-> {path}')
        else:seen[key]=path
    return out
def audit(root:Path)->list[str]:return audit_paths(tracked_files(require_root(root)))
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',nargs='?',default='.');return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=='__main__':raise SystemExit(main())
