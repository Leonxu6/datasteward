from scripts.audit_subprocess_run_check import audit_source


def test_subprocess_run_audit_allows_checked_execution():
    assert audit_source("subprocess.run(cmd, check=True)\n") == []


def test_subprocess_run_audit_reports_unchecked_execution():
    assert audit_source("subprocess.run(cmd)\n") == [
        "subprocess.run() without check=True on line 1; handle non-zero exits explicitly"
    ]
