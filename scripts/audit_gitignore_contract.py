"""Verify DataSteward's privacy and generated-data ignore rules stay intact."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.audit_common import print_failures, require_root

_REQUIRED = {"data/", "logs/", "*.jsonl", "rag_docs/", "__pycache__/", ".venv/", ".env", "*.duckdb", "transform/dbt/target/", "transform/dbt/dbt_packages/", "*.docx", ".DS_Store"}


def audit(root: Path) -> list[str]:
    root = require_root(root)
    try:
        lines = {line.strip() for line in (root / ".gitignore").read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")}
    except (OSError, UnicodeError) as exc:
        return [f".gitignore: could not read ignore rules ({exc})"]
    return [f".gitignore: missing required rule {rule}" for rule in sorted(_REQUIRED - lines)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    return print_failures(audit(Path(args.root)))


if __name__ == "__main__":
    raise SystemExit(main())
