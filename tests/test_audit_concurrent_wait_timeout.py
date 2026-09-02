from scripts.audit_concurrent_wait_timeout import audit_source

def test_wait_timeout_allows_bounded_waits():
    assert audit_source("concurrent.futures.wait(fs, timeout=2)\n") == []

def test_wait_timeout_reports_unbounded_waits():
    assert audit_source("concurrent.futures.wait(fs)\n") == ["concurrent futures wait without timeout on line 1"]
