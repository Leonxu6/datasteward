from scripts.audit_httpx_timeout import audit_source


def test_httpx_timeout_audit_allows_explicit_timeout():
    assert audit_source("httpx.get(url, timeout=10)\n") == []


def test_httpx_timeout_audit_reports_missing_timeout():
    assert audit_source("httpx.AsyncClient()\n") == ["httpx.AsyncClient() without explicit timeout on line 1"]
