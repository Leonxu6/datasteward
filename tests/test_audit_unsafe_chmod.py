from scripts.audit_unsafe_chmod import audit_source


def test_unsafe_chmod_audit_allows_owner_only_write_modes():
    assert audit_source("os.chmod(path, 0o600)\n") == []


def test_unsafe_chmod_audit_reports_world_writable_modes():
    assert audit_source("os.chmod(path, 0o666)\n") == [
        "world-writable chmod mode 0o666 on line 1"
    ]
