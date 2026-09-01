from scripts.audit_sqlite_shared_cache import audit_source


def test_shared_cache_audit_allows_connection_options():
    assert audit_source("sqlite3.connect(path, cache='shared')\n") == []


def test_shared_cache_audit_reports_global_policy_changes():
    assert audit_source("sqlite3.enable_shared_cache(True)\n") == ["sqlite3.enable_shared_cache() mutates global SQLite connection policy on line 1"]
