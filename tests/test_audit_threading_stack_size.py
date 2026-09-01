from scripts.audit_threading_stack_size import audit_source


def test_stack_size_audit_allows_reading_current_default():
    assert audit_source("threading.stack_size()\n") == []


def test_stack_size_audit_reports_default_stack_mutation():
    assert audit_source("threading.stack_size(1024 * 1024)\n") == ["threading.stack_size() mutates the default thread stack on line 1"]
