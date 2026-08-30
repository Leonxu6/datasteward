from scripts.audit_unbounded_deque import audit_source


def test_deque_audit_allows_maxlen():
    assert audit_source("collections.deque(maxlen=128)\n") == []


def test_deque_audit_reports_missing_maxlen():
    assert audit_source("collections.deque()\n") == ["collections.deque() without maxlen on line 1"]
