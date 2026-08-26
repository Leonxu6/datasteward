"""Validate tracked TOML files using the standard parser."""
from __future__ import annotations
import argparse,tomllib
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files

def audit_file(path:Path)->list[str]:
    try:
        with path.open("rb") as f: tomllib.load(f)
    except (OSError,tomllib.TOMLDecodeError) as exc:return [f"invalid TOML: {exc}"]
    return []

def audit(root:Path)->list[str]:
    root=require_root(root); failures=[]
    for rel in tracked_files(root):
        if rel.suffix.lower()==".toml": failures.extend(f"{rel}: {x}" for x in audit_file(root/rel))
    return failures

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("root",nargs="?",default=".");return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__":raise SystemExit(main())
