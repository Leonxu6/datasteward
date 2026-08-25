"""Check pytest modules follow predictable discovery naming."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.audit_common import print_failures, require_root, tracked_files


def audit_paths(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        if path.parts and path.parts[0] == "tests" and path.suffix == ".py" and path.name != "__init__.py" and not path.name.startswith("test_"):
            failures.append(f"{path}: test module must start with test_")
    return failures


def audit(root: Path) -> list[str]:
    root = require_root(root)
    failures = audit_paths(tracked_files(root))
    if not (root / "tests").is_dir(): failures.append("tests: test directory is missing")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv); return print_failures(audit(Path(args.root)))


if __name__ == "__main__": raise SystemExit(main())
