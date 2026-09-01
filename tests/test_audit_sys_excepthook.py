from scripts.audit_sys_excepthook import audit_source


def test_sys_excepthook_audit_allows_local_handlers():
    assert audit_source("handler = report_error\n") == []


def test_sys_excepthook_audit_reports_process_hook_replacement():
    assert audit_source("sys.excepthook = report_error\n") == ["sys.excepthook replacement mutates process error handling on line 1"]
