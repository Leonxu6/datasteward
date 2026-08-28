from scripts.audit_os_chdir import audit_source


def test_chdir_audit_allows_path_scoped_operations():
    assert audit_source("target = root / 'data'\n") == []


def test_chdir_audit_reports_process_mutation():
    assert audit_source("os.chdir(target)\n") == ["os.chdir() mutates process-wide state on line 1"]
