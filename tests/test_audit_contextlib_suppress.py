from scripts.audit_contextlib_suppress import audit_source


def test_suppress_audit_allows_specific_exceptions():
    assert audit_source("with contextlib.suppress(FileNotFoundError):\n    pass\n") == []


def test_suppress_audit_reports_broad_exceptions():
    assert audit_source("with contextlib.suppress(Exception):\n    pass\n") == [
        "broad contextlib.suppress() on line 1"
    ]
