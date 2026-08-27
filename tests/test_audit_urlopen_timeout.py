from scripts.audit_urlopen_timeout import audit_source


def test_urlopen_timeout_audit_allows_explicit_timeout():
    assert audit_source("urllib.request.urlopen(url, timeout=5)\n") == []


def test_urlopen_timeout_audit_reports_missing_timeout():
    assert audit_source("urllib.request.urlopen(url)\n") == [
        "urlopen() without timeout on line 1"
    ]
