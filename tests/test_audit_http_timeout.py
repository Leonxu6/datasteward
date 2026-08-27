from scripts.audit_http_timeout import audit_source


def test_http_timeout_audit_allows_explicit_timeout():
    assert audit_source("requests.get(url, timeout=5)\n") == []


def test_http_timeout_audit_reports_missing_timeout():
    failures = audit_source("requests.get(url)\nhttpx.post(url, json=data)\n")
    assert failures == [
        "requests.get() without timeout on line 1",
        "httpx.post() without timeout on line 2",
    ]
