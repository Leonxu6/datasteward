from scripts.audit_sqlite_timeout import audit_source


def test_sqlite_timeout_audit_allows_explicit_timeout():
    assert audit_source("sqlite3.connect(path, timeout=10)\n") == []


def test_sqlite_timeout_audit_reports_implicit_timeout():
    assert audit_source("sqlite3.connect(path)\n") == ["sqlite3.connect() without explicit timeout on line 1"]
