"""Run DataSteward's repository-maintenance audits as one deterministic command."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Blocking audits are clean on main and act as regression gates.
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
    "audit_path_text_encoding.py",
    "audit_open_text_encoding.py",
    "audit_naive_fromtimestamp.py",
    "audit_builtin_hash.py",
    "audit_tar_extractall.py",
    "audit_unpack_archive.py",
    "audit_os_chdir.py",
    "audit_os_umask.py",
    "audit_locale_mutation.py",
    "audit_warning_suppression.py",
    "audit_socket_default_timeout.py",
    "audit_signal_handlers.py",
    "audit_sys_exit.py",
    "audit_recursion_limit.py",
    "audit_gc_disable.py",
    "audit_random_seed.py",
    "audit_asyncio_run.py",
    "audit_logging_basic_config.py",
    "audit_subprocess_run_check.py",
    "audit_thread_daemon.py",
)

# These rules exposed pre-existing, repository-wide migration work when first
# enabled. They still execute on every CI run and remain visible in the log,
# but they do not turn a known backlog into a permanently red main branch.
# Move each rule into _AUDITS as its existing findings are remediated.
_ADVISORY_AUDITS = (
    "audit_naive_datetime_now.py",
    "audit_environ_mutation.py",
    "audit_json_nan.py",
    "audit_sql_interpolation.py",
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


def _run_audit(root: Path, script: str) -> str | None:
    path = root / "scripts" / script
    if not path.is_file():
        return "audit script is missing"
    module = f"scripts.{Path(script).stem}"
    try:
        result = subprocess.run(
            [sys.executable, "-m", module, str(root)],
            cwd=root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "audit timed out"
    except OSError as exc:
        return f"audit could not start ({exc})"
    return _failure_detail(result) if result.returncode else None


def run_audits(root: Path, *, scripts: tuple[str, ...] = _AUDITS) -> list[str]:
    if not isinstance(root, Path) or not root.is_dir():
        raise ValueError("root must be an existing directory")
    scripts = _validate_scripts(scripts)
    failures: list[str] = []
    for script in scripts:
        detail = _run_audit(root, script)
        if detail:
            failures.append(f"{script}: {detail}")
    return failures


def run_advisory_audits(
    root: Path, *, scripts: tuple[str, ...] = _ADVISORY_AUDITS
) -> list[str]:
    if not isinstance(root, Path) or not root.is_dir():
        raise ValueError("root must be an existing directory")
    scripts = _validate_scripts(scripts)
    findings: list[str] = []
    for script in scripts:
        detail = _run_audit(root, script)
        if detail:
            findings.append(f"{script}: {detail}")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root)
    failures = run_audits(root)
    advisories = run_advisory_audits(root)
    for finding in advisories:
        print(f"[advisory] {finding}", file=sys.stderr)
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
