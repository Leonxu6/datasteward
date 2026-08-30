from scripts.audit_aiohttp_timeout import audit_source


def test_aiohttp_timeout_audit_allows_explicit_timeout():
    assert audit_source("aiohttp.ClientSession(timeout=timeout)\n") == []


def test_aiohttp_timeout_audit_reports_missing_timeout():
    assert audit_source("aiohttp.ClientSession()\n") == ["aiohttp.ClientSession() without explicit timeout on line 1"]
