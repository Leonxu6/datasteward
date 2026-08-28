from scripts.audit_sys_exit import audit_source


def test_sys_exit_audit_allows_domain_errors():
    assert audit_source("raise ValueError('bad input')\n") == []


def test_sys_exit_audit_reports_process_termination():
    assert audit_source("sys.exit(2)\n") == ["sys.exit() terminates the hosting process on line 1"]
