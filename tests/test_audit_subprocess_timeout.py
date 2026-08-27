from scripts.audit_subprocess_timeout import audit_source


def test_subprocess_timeout_audit_allows_bounded_calls():
    assert audit_source("subprocess.run(['tool'], timeout=10)\n") == []


def test_subprocess_timeout_audit_reports_unbounded_calls():
    failures = audit_source("subprocess.run(['tool'])\nsubprocess.check_output(['tool'])\n")
    assert failures == [
        "subprocess.run() without timeout on line 1",
        "subprocess.check_output() without timeout on line 2",
    ]
