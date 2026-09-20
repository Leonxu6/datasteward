"""Validate tracked TOML files using the standard parser."""
from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from scripts.audit_common import print_failures, require_root, tracked_files

_MAX_TOML_BYTES = 2 * 1024 * 1024


def audit_file(path: Path) -> list[str]:
    if path.is_symlink():
        return [f"invalid TOML: {path.name}: symbolic links are not accepted"]
    if not path.is_file():
        return [f"invalid TOML: {path.name}: expected a regular file"]
    try:
        if path.stat().st_size > _MAX_TOML_BYTES:
            return [f"invalid TOML: {path.name}: file exceeds {_MAX_TOML_BYTES} byte audit limit"]
        with path.open("rb") as handle:
            tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"invalid TOML: {path.name}: {exc}"]
    return []


def audit(root: Path) -> list[str]:
    root = require_root(root)
    failures: list[str] = []
    for rel in tracked_files(root):
        if rel.suffix.lower() == ".toml":
            failures.extend(f"{rel}: {item}" for item in audit_file(root / rel))
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    return print_failures(audit(Path(parser.parse_args(argv).root)))


if __name__ == "__main__":
    raise SystemExit(main())
