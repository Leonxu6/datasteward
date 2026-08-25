"""Run DataSteward's repository-maintenance audits as one deterministic command."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_AUDITS = (
    "audit_ci_contract.py",
    "audit_docs_contract.py",
    "audit_entrypoints.py",
    "audit_env_example.py",
    "audit_gitignore_contract.py",
    "audit_markdown_links.py",
    "audit_path_case.py",
    "audit_pyproject_metadata.py",
    "audit_python_compile.py",
    "audit_repository_hygiene.py",
    "audit_secret_filenames.py",
    "audit_sensitive.py",
    "audit_source_layout.py",
    "audit_test_layout.py",
    "audit_text_integrity.py",
    "audit_workflow_security.py",
)


def _validate_scripts(scripts: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(scripts, tuple):
        raise ValueError("scripts must be a tuple of audit filenames")
    seen: set[str] = set()
    for script in scripts:
        if (
            not isinstance(script, str)
            or not script
            or script != script.strip()
            or not script.endswith(".py")
            or "/" in script
            or "\\" in script
        ):
            raise ValueError("audit script names must be simple .py filenames")
        if script in seen:
            raise ValueError("audit script names must be unique")
        seen.add(script)
    return scripts


def run_audits(root: Path, *, scripts: tuple[str, ...] = _AUDITS) -> list[str]:
    if not isinstance(root, Path) or not root.is_dir():
        raise ValueError("root must be an existing directory")
    scripts = _validate_scripts(scripts)
    failures: list[str] = []
    script_dir = root / "scripts"
    for script in scripts:
        path = script_dir / script
        if not path.is_file():
            failures.append(f"{script}: audit script is missing")
            continue
        try:
            result = subprocess.run(
                [sys.executable, str(path), str(root)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{script}: audit timed out")
            continue
        except OSError as exc:
            failures.append(f"{script}: audit could not start ({exc})")
            continue
        if result.returncode:
            detail = " ".join((result.stdout or result.stderr or "audit failed").split())[:1000]
            failures.append(f"{script}: {detail}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    failures = run_audits(Path(args.root))
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
