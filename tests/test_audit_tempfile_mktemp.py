from scripts.audit_tempfile_mktemp import audit_source


def test_tempfile_audit_allows_secure_creation():
    assert audit_source("tempfile.NamedTemporaryFile()\n") == []


def test_tempfile_audit_reports_mktemp():
    assert audit_source("tempfile.mktemp()\n") == ["tempfile.mktemp() on line 1"]
