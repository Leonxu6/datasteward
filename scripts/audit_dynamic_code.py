"""Flag direct eval/exec calls in tracked Python source."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files

def audit_source(source:str)->list[str]:
    try:tree=ast.parse(source)
    except SyntaxError:return []
    return [f"dynamic code execution via {n.func.id}() on line {n.lineno}" for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {"eval","exec"}]
def audit(root:Path)->list[str]:
    root=require_root(root);failures=[]
    for rel in tracked_files(root):
        if rel.suffix!=".py":continue
        try:source=(root/rel).read_text(encoding="utf-8")
        except (OSError,UnicodeDecodeError):continue
        failures.extend(f"{rel}: {x}" for x in audit_source(source))
    return failures
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("root",nargs="?",default=".");return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__":raise SystemExit(main())
