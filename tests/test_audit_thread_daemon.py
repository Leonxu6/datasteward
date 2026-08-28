from scripts.audit_thread_daemon import audit_source


def test_thread_audit_allows_explicit_lifecycle_policy():
    assert audit_source("threading.Thread(target=worker, daemon=False)\n") == []


def test_thread_audit_reports_implicit_lifecycle():
    assert audit_source("threading.Thread(target=worker)\n") == [
        "threading.Thread() without explicit daemon policy on line 1"
    ]
