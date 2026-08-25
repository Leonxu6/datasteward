"""Validate DataSteward package metadata and entrypoint declarations."""
from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from scripts.audit_common import print_failures, require_root

_REQUIRED_SCRIPTS = {"dm-load", "dm-agent", "dm-app", "dm-eval", "dm-dingtalk", "dm-docs", "dm-kg", "dm-connect", "dm-u8"}


def audit(root: Path) -> list[str]:
    root = require_root(root)
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        return [f"pyproject.toml: could not parse project metadata ({exc})"]
    project = data.get("project")
    if not isinstance(project, dict):
        return ["pyproject.toml: [project] table is missing"]
    failures: list[str] = []
    if project.get("name") != "datasteward": failures.append("pyproject.toml: project name must remain datasteward")
    if project.get("license") != {"text": "Apache-2.0"}: failures.append("pyproject.toml: Apache-2.0 license metadata is required")
    if project.get("requires-python") != ">=3.10": failures.append("pyproject.toml: requires-python must remain >=3.10")
    scripts = project.get("scripts")
    if not isinstance(scripts, dict): failures.append("pyproject.toml: [project.scripts] table is missing")
    else:
        for name in sorted(_REQUIRED_SCRIPTS - set(scripts)):
            failures.append(f"pyproject.toml: missing CLI entrypoint {name}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv); return print_failures(audit(Path(args.root)))


if __name__ == "__main__": raise SystemExit(main())
