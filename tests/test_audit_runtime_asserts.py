from scripts.audit_runtime_asserts import audit_source


def test_runtime_assert_audit_allows_explicit_validation():
    assert audit_source("if not ready:\n    raise ValueError('not ready')\n") == []


def test_runtime_assert_audit_reports_assert_statements():
    assert audit_source("assert ready, 'not ready'\n") == [
        "runtime assert on line 1; use explicit validation instead"
    ]
