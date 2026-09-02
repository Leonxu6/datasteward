from scripts.audit_os_exec import audit_source

def test_os_exec_ignores_process_queries():
    assert audit_source("os.getpid()\n") == []

def test_os_exec_reports_process_replacement():
    assert audit_source("os.execv(path, argv)\n") == ["os.execv replaces the current process on line 1"]
