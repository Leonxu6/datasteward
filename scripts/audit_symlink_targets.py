"""Ensure tracked symlinks resolve inside the repository tree."""
from __future__ import annotations
import argparse
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files

def audit(root:Path)->list[str]:
    root=require_root(root).resolve();out=[]
    for rel in tracked_files(root):
        path=root/rel
        if not path.is_symlink():continue
        try:resolved=path.resolve(strict=False);resolved.relative_to(root)
        except (OSError,ValueError,RuntimeError):out.append(f'{rel}: symlink target escapes repository')
    return out
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',nargs='?',default='.');return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=='__main__':raise SystemExit(main())
