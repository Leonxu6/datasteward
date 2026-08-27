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
    "audit_json_syntax.py",
    "audit_toml_syntax.py",
    "audit_unicode_bidi.py",
    "audit_dynamic_code.py",
    "audit_subprocess_shell.py",
    "audit_unsafe_deserialization.py",
    "audit_weak_hash.py",
    "audit_tls_verification.py",
    "audit_tempfile_safety.py",
    "audit_dependency_sources.py",
    "audit_markdown_fences.py",
    "audit_merge_markers.py",
    "audit_yaml_loading.py",
    "audit_unicode_paths.py",
    "audit_symlink_targets.py",
    "audit_bare_except.py",
    "audit_mutable_default.py",
    "audit_wildcard_import.py",
    "audit_debug_calls.py",
    "audit_os_system.py",
    "audit_datetime_utcnow.py",
    "audit_absolute_user_paths.py",
    "audit_duplicate_definitions.py",
    "audit_unsafe_chmod.py",
    "audit_http_timeout.py",
    "audit_urlopen_timeout.py",
    "audit_subprocess_timeout.py",
    "audit_async_blocking_sleep.py",
    "audit_async_subprocess.py",
    "audit_runtime_asserts.py",
    "audit_baseexception_handlers.py",
    "audit_sys_path_mutation.py",
    "audit_interactive_input.py",
    "audit_unverified_ssl_context.py",
    "audit_uuid1.py",
    "audit_socket_timeout.py",
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


def _failure_detail(result: object) -> str:
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    detail = " ".join(f"{stdout}\n{stderr}".split()) or "audit failed"
    return detail[:1000]


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
        module = f"scripts.{Path(script).stem}"
        try:
            result = subprocess.run(
                [sys.executable, "-m", module, str(root)],
                cwd=root,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{script}: audit timed out")
            continue
        except OSError as exc:
            failures.append(f"{script}: audit could not start ({exc})")
            continue
        if result.returncode:
            failures.append(f"{script}: {_failure_detail(result)}")
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
