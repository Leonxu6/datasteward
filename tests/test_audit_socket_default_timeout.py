from scripts.audit_socket_default_timeout import audit_source


def test_socket_timeout_audit_allows_per_call_timeouts():
    assert audit_source("socket.create_connection(addr, timeout=5)\n") == []


def test_socket_timeout_audit_reports_global_default():
    assert audit_source("socket.setdefaulttimeout(5)\n") == [
        "socket.setdefaulttimeout() mutates process-wide networking on line 1"
    ]
