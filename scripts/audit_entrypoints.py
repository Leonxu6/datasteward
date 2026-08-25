"""Verify console-script targets resolve to real top-level callables in src/dm."""
from __future__ import annotations

import argparse
import ast
import tomllib
from pathlib import Path

from scripts.audit_common import print_failures, require_root


def _target_path(root: Path, module: str) -> Path:
    parts = module.split(".")
    if not parts or parts[0] != "dm" or any(not part.isidentifier() for part in parts):
        raise ValueError(f"unsupported entrypoint module: {module}")
    return root / "src" / Path(*parts).with_suffix(".py")


def audit(root: Path) -> list[str]:
    root = require_root(root)
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        return [f"pyproject.toml: could not parse entrypoints ({exc})"]
    scripts = data.get("project", {}).get("scripts", {})
    if not isinstance(scripts, dict):
        return ["pyproject.toml: [project.scripts] table is missing"]
    failures: list[str] = []
    for name, target in sorted(scripts.items()):
        if not isinstance(target, str) or target.count(":") != 1:
            failures.append(f"{name}: entrypoint must use module:function syntax"); continue
        module, function = target.split(":", 1)
        if not function.isidentifier():
            failures.append(f"{name}: invalid entrypoint function {function!r}"); continue
        try: path = _target_path(root, module)
        except ValueError as exc: failures.append(f"{name}: {exc}"); continue
        if not path.is_file():
            failures.append(f"{name}: entrypoint module is missing: {path.relative_to(root)}"); continue
        try: tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            failures.append(f"{name}: could not parse entrypoint module ({exc})"); continue
        if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function for node in tree.body):
            failures.append(f"{name}: top-level callable {function} is missing in {path.relative_to(root)}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv); return print_failures(audit(Path(args.root)))


if __name__ == "__main__": raise SystemExit(main())
