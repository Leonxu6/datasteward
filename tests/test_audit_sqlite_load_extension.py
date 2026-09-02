from scripts.audit_sqlite_load_extension import audit_source

def test_sqlite_extension_audit_allows_disabled_loading():
    assert audit_source("conn.enable_load_extension(False)\n") == []

def test_sqlite_extension_audit_reports_native_extension_load():
    assert audit_source("conn.load_extension(path)\n") == ["SQLite load_extension executes native code on line 1"]
