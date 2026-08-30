from scripts.audit_os_putenv import audit_source


def test_putenv_audit_allows_environment_reads():
    assert audit_source("os.getenv('MODE')\n") == []


def test_putenv_audit_reports_process_mutation():
    assert audit_source("os.putenv('MODE', 'prod')\n") == ["os.putenv() mutates process environment on line 1"]
