"""Detect unresolved Git conflict markers in tracked text."""
from __future__ import annotations
import argparse
from pathlib import Path
from scripts.audit_common import TEXT_SUFFIXES,print_failures,require_root,tracked_files

def audit_text(text:str)->list[str]:
    left='< '*0+'<'*7;right='>'*7
    return [f'unresolved merge marker on line {i}' for i,line in enumerate(text.splitlines(),1) if line.startswith(left) or line.startswith(right)]
def audit(root:Path)->list[str]:
    root=require_root(root);out=[]
    for rel in tracked_files(root):
        if rel.suffix.lower() not in TEXT_SUFFIXES:continue
        try:text=(root/rel).read_text(encoding='utf-8')
        except (OSError,UnicodeDecodeError):continue
        out.extend(f'{rel}: {x}' for x in audit_text(text))
    return out
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',nargs='?',default='.');return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=='__main__':raise SystemExit(main())
