from scripts.audit_websocket_timeout import audit_source


def test_websocket_audit_allows_open_timeout():
    assert audit_source("websockets.connect(url, open_timeout=10)\n") == []


def test_websocket_audit_reports_missing_timeout():
    assert audit_source("websockets.connect(url)\n") == ["websockets.connect() without open_timeout on line 1"]
