"""Detect subprocess calls with shell=True."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
from scripts.audit_common import print_failures,require_root,tracked_files
_CALLS={"run","Popen","call","check_call","check_output"}
def audit_source(source:str)->list[str]:
    try:tree=ast.parse(source)
    except SyntaxError:return []
    failures=[]
    for n in ast.walk(tree):
        if not(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in _CALLS and isinstance(n.func.value,ast.Name) and n.func.value.id=="subprocess"):continue
        if any(k.arg=="shell" and isinstance(k.value,ast.Constant) and k.value.value is True for k in n.keywords):failures.append(f"subprocess shell=True on line {n.lineno}")
    return failures
def audit(root:Path)->list[str]:
    root=require_root(root);failures=[]
    for rel in tracked_files(root):
        if rel.suffix!=".py":continue
        try:s=(root/rel).read_text(encoding="utf-8")
        except (OSError,UnicodeDecodeError):continue
        failures.extend(f"{rel}: {x}" for x in audit_source(s))
    return failures
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("root",nargs="?",default=".");return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__":raise SystemExit(main())
