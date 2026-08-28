from scripts.audit_naive_fromtimestamp import audit_source


def test_fromtimestamp_allows_timezone():
    assert audit_source("datetime.fromtimestamp(ts, timezone.utc)\n") == []


def test_fromtimestamp_reports_naive_call():
    assert audit_source("datetime.fromtimestamp(ts)\n") == ["datetime.fromtimestamp() without timezone on line 1"]
