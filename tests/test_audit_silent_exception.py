from scripts.audit_silent_exception import audit_source


def test_silent_exception_audit_allows_handled_errors():
    assert audit_source("try:\n    work()\nexcept Exception:\n    log_error()\n") == []


def test_silent_exception_audit_reports_pass_only_handlers():
    assert audit_source("try:\n    work()\nexcept Exception:\n    pass\n") == [
        "exception handler silently passes on line 3"
    ]
