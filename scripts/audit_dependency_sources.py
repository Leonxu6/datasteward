"""Reject direct URL/VCS project dependencies that bypass index review."""
from __future__ import annotations
import argparse,tomllib
from pathlib import Path
from scripts.audit_common import print_failures,require_root

def audit_dependencies(deps:object)->list[str]:
    if not isinstance(deps,list):return ['project.dependencies must be a list']
    out=[]
    for item in deps:
        if not isinstance(item,str):out.append('project dependency entries must be strings');continue
        low=item.lower()
        if ' @ ' in item or low.startswith(('git+','file:','http://','https://')):out.append(f'direct dependency source is not allowed: {item}')
    return out
def audit(root:Path)->list[str]:
    root=require_root(root)
    try:
        with (root/'pyproject.toml').open('rb') as f:data=tomllib.load(f)
    except (OSError,tomllib.TOMLDecodeError) as exc:return [f'could not parse pyproject.toml: {exc}']
    project=data.get('project');return ['pyproject.toml is missing [project]'] if not isinstance(project,dict) else audit_dependencies(project.get('dependencies',[]))
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',nargs='?',default='.');return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=='__main__':raise SystemExit(main())
