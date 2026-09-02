from scripts.audit_os_forkpty import audit_source

def test_os_forkpty_ignores_terminal_queries():
    assert audit_source("os.ttyname(fd)\n") == []

def test_os_forkpty_reports_process_fork():
    assert audit_source("os.forkpty()\n") == ["os.forkpty requires explicit process and terminal lifecycle review on line 1"]
