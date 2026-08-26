"""Detect unbalanced fenced code blocks in tracked Markdown."""
from __future__ import annotations
import argparse
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files

def audit_text(text:str)->list[str]:
    fence=None;opening=0
    for i,line in enumerate(text.splitlines(),1):
        s=line.lstrip();marker='```' if s.startswith('```') else '~~~' if s.startswith('~~~') else None
        if marker is None:continue
        if fence is None:fence=marker;opening=i
        elif marker==fence:fence=None;opening=0
    return [f'unclosed Markdown fence opened on line {opening}'] if fence else []
def audit(root:Path)->list[str]:
    root=require_root(root);out=[]
    for rel in tracked_files(root):
        if rel.suffix.lower()!='.md':continue
        try:text=(root/rel).read_text(encoding='utf-8')
        except (OSError,UnicodeDecodeError) as exc:out.append(f'{rel}: could not read Markdown ({exc})');continue
        out.extend(f'{rel}: {x}' for x in audit_text(text))
    return out
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',nargs='?',default='.');return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=='__main__':raise SystemExit(main())
