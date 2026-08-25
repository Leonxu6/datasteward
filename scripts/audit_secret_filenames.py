"""Flag tracked filenames that commonly contain credentials or private keys."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.audit_common import print_failures, require_root, tracked_files

_SECRET_NAMES = {"credentials.json", "service-account.json", "id_rsa", "id_ed25519", ".env", "role_map.yaml"}
_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


def audit_paths(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        if path.name.lower() in _SECRET_NAMES or path.suffix.lower() in _SECRET_SUFFIXES:
            failures.append(f"{path}: credential-like file must not be tracked")
    return failures


def audit(root: Path) -> list[str]:
    require_root(root); return audit_paths(tracked_files(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv); return print_failures(audit(Path(args.root)))


if __name__ == "__main__": raise SystemExit(main())
