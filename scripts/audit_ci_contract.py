#!/usr/bin/env python3
"""Check the repository's minimum CI contract from workflow text."""
from __future__ import annotations

from pathlib import Path

_REQUIRED = {
    "main push trigger": "branches: [main]",
    "pull request trigger": "pull_request:",
    "unit tests": "pytest -m \"not integration and not stack\" -q",
    "dbt parse": "dbt parse",
    "compose validation": "docker compose -f deploy/docker-compose.yml config -q",
    "maintenance audits": "python -m scripts.run_maintenance_audits",
}


def missing_ci_contract(path: Path) -> tuple[str, ...]:
    text = path.read_text(encoding="utf-8")
    return tuple(name for name, needle in _REQUIRED.items() if needle not in text)


def main() -> int:
    path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    missing = missing_ci_contract(path)
    if missing:
        print("Missing CI contract elements: " + ", ".join(missing))
        return 1
    print("CI contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
