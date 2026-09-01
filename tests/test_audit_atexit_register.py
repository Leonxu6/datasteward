from scripts.audit_atexit_register import audit_source


def test_atexit_audit_allows_local_cleanup_calls():
    assert audit_source("cleanup()\n") == []


def test_atexit_audit_reports_process_shutdown_hooks():
    assert audit_source("atexit.register(cleanup)\n") == ["atexit.register() mutates process shutdown behavior on line 1"]
