from scripts.audit_bare_except import audit_source


def test_bare_except_audit_allows_typed_handlers():
    assert audit_source("try:\n    work()\nexcept Exception:\n    recover()\n") == []


def test_bare_except_audit_reports_untyped_handlers():
    assert audit_source("try:\n    work()\nexcept:\n    recover()\n") == [
        "bare except handler on line 3"
    ]
