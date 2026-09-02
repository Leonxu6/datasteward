from scripts.audit_as_completed_timeout import audit_source

def test_as_completed_allows_timeout():
    assert audit_source("concurrent.futures.as_completed(fs, timeout=5)\n") == []

def test_as_completed_reports_missing_timeout():
    assert audit_source("concurrent.futures.as_completed(fs)\n") == ["as_completed without timeout on line 1"]
