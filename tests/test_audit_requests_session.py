from scripts.audit_requests_session import audit_source


def test_requests_session_audit_allows_stateless_calls():
    assert audit_source("requests.get(url, timeout=10)\n") == []


def test_requests_session_audit_reports_owned_sessions():
    assert audit_source("requests.Session()\n") == ["requests.Session() needs explicit lifecycle on line 1"]
