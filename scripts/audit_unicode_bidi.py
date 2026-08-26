"""Detect bidirectional Unicode controls that can disguise tracked text."""
from __future__ import annotations
import argparse
from pathlib import Path
from scripts.audit_common import TEXT_SUFFIXES,print_failures,require_root,tracked_files
_BIDI={"\u061c","\u200e","\u200f","\u202a","\u202b","\u202c","\u202d","\u202e","\u2066","\u2067","\u2068","\u2069"}
def audit_text(text:str)->list[str]:
    return [f"bidirectional control character on line {i}" for i,line in enumerate(text.splitlines(),1) if any(c in _BIDI for c in line)]
def audit(root:Path)->list[str]:
    root=require_root(root);failures=[]
    for rel in tracked_files(root):
        if rel.suffix.lower() not in TEXT_SUFFIXES:continue
        try:text=(root/rel).read_text(encoding="utf-8")
        except (OSError,UnicodeDecodeError):continue
        failures.extend(f"{rel}: {x}" for x in audit_text(text))
    return failures
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("root",nargs="?",default=".");return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__":raise SystemExit(main())
