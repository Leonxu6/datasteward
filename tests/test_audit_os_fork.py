from scripts.audit_os_fork import audit_source

def test_os_fork_ignores_process_queries():
    assert audit_source("os.getpid()\n") == []

def test_os_fork_reports_direct_fork():
    assert audit_source("os.fork()\n") == ["os.fork requires explicit lifecycle review on line 1"]
