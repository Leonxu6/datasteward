from scripts.audit_os_umask import audit_source


def test_umask_audit_allows_explicit_file_modes():
    assert audit_source("os.open(path, flags, 0o600)\n") == []


def test_umask_audit_reports_process_mutation():
    assert audit_source("os.umask(0o077)\n") == ["os.umask() mutates process-wide permissions on line 1"]
