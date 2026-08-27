from scripts.audit_baseexception_handlers import audit_source


def test_baseexception_audit_allows_exception_handlers():
    assert audit_source("try:\n    work()\nexcept Exception:\n    recover()\n") == []


def test_baseexception_audit_reports_direct_and_tuple_handlers():
    source = "try:\n    work()\nexcept (ValueError, BaseException):\n    recover()\n"
    assert audit_source(source) == [
        "BaseException handler on line 3; catch a narrower exception"
    ]
