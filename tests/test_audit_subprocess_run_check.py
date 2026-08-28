from scripts.audit_subprocess_run_check import audit_source


def test_subprocess_run_audit_allows_checked_execution():
    assert audit_source("subprocess.run(cmd, check=True)\n") == []


def test_subprocess_run_audit_allows_explicit_manual_return_code_handling():
    assert audit_source("result = subprocess.run(cmd, check=False)\nif result.returncode:\n    raise RuntimeError\n") == []


def test_subprocess_run_audit_reports_implicit_failure_policy():
    assert audit_source("subprocess.run(cmd)\n") == [
        "subprocess.run() without explicit check policy on line 1; use check=True or check=False with explicit return-code handling"
    ]
