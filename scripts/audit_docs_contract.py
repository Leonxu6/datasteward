"""Check that core operator and contributor documentation remains substantive."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.audit_common import print_failures, require_root

_REQUIRED = {
    "README.md": 1500,
    "CONTRIBUTING.md": 400,
    "docs/operations/configuration.md": 500,
    "docs/operations/connectors.md": 500,
    "docs/operations/data-health.md": 500,
    "docs/operations/deployment.md": 500,
    "docs/operations/local-development.md": 500,
    "docs/operations/security.md": 500,
    "docs/operations/troubleshooting.md": 500,
    "docs/operations/warehouse.md": 500,
}


def audit(root: Path) -> list[str]:
    root = require_root(root)
    failures: list[str] = []
    for rel, minimum in _REQUIRED.items():
        path = root / rel
        if not path.is_file():
            failures.append(f"{rel}: required maintainer documentation is missing")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"{rel}: unreadable documentation ({exc})")
            continue
        if len(text.strip()) < minimum:
            failures.append(f"{rel}: documentation is unexpectedly small")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    return print_failures(audit(Path(args.root)))


if __name__ == "__main__":
    raise SystemExit(main())
