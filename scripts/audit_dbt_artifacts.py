#!/usr/bin/env python3
"""Validate dbt artifact JSON shapes without connecting to a database."""
from __future__ import annotations

import json
from pathlib import Path


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    output: dict = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON object key: {key}")
        output[key] = value
    return output


def validate_artifact(path: Path) -> list[str]:
    if not path.exists():
        return [f"missing artifact: {path.name}"]
    if not path.is_file():
        return [f"artifact is not a file: {path.name}"]
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonstandard_constant,
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"invalid JSON in {path.name}: {exc}"]
    if not isinstance(data, dict):
        return [f"{path.name} must contain a JSON object"]
    if path.name == "manifest.json":
        issues = []
        for key in ("nodes", "sources"):
            if key not in data:
                issues.append(f"manifest.json missing '{key}'")
            elif not isinstance(data[key], dict):
                issues.append(f"manifest.json '{key}' must be an object")
        return issues
    if path.name == "run_results.json":
        results = data.get("results")
        return [] if isinstance(results, list) else ["run_results.json 'results' must be an array"]
    return [f"unsupported dbt artifact: {path.name}"]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    target = root / "transform" / "dbt" / "target"
    paths = (target / "manifest.json", target / "run_results.json")
    issues = [issue for path in paths for issue in validate_artifact(path)]
    for issue in issues:
        print(issue)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
