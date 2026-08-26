"""Validate tracked JSON files without importing application code."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from scripts.audit_common import print_failures, require_root, tracked_files

def audit_file(path: Path) -> list[str]:
    try: json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc: return [f"invalid JSON: {exc}"]
    return []

def audit(root: Path) -> list[str]:
    root=require_root(root); failures=[]
    for rel in tracked_files(root):
        if rel.suffix.lower()==".json": failures.extend(f"{rel}: {x}" for x in audit_file(root/rel))
    return failures

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("root",nargs="?",default="."); return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__": raise SystemExit(main())
