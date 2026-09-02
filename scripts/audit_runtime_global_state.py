"""Detect process-wide runtime mutations in DataSteward production modules.

This audit starts as advisory because global-state APIs can appear in legitimate
integration code. Findings make those decisions visible before a future change
silently alters unrelated workers in the same process.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.audit_ast_rules import call_name, iter_calls
from scripts.audit_common import print_failures, production_python_files, require_root

_RULE_MESSAGES = {
    "faulthandler.enable": "faulthandler configuration is process-wide",
    "faulthandler.disable": "faulthandler configuration is process-wide",
    "faulthandler.register": "faulthandler signal registration is process-wide",
    "faulthandler.unregister": "faulthandler signal registration is process-wide",
    "tracemalloc.start": "tracemalloc lifecycle is process-wide",
    "tracemalloc.stop": "tracemalloc lifecycle is process-wide",
    "tracemalloc.clear_traces": "tracemalloc traces are process-wide",
}


def findings_for_source(source: str, *, path: str = "<memory>") -> list[str]:
    if not isinstance(source, str):
        raise ValueError("source must be text")
    if not isinstance(path, str) or not path or path != path.strip():
        raise ValueError("path must be clean non-empty text")
    findings: list[str] = []
    for call in iter_calls(source):
        name = call_name(call)
        detail = _RULE_MESSAGES.get(name or "")
        if detail:
            findings.append(f"{path}:{call.lineno}: {name}: {detail}")
    return findings


def audit(root: Path) -> list[str]:
    root = require_root(root)
    findings: list[str] = []
    for rel in production_python_files(root):
        path = root / rel
        if path.is_symlink():
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append(f"{rel}: unreadable source ({exc.__class__.__name__})")
            continue
        findings.extend(findings_for_source(source, path=rel.as_posix()))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    return print_failures(audit(Path(args.root)))


if __name__ == "__main__":
    raise SystemExit(main())
