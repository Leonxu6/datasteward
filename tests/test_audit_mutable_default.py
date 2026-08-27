from scripts.audit_mutable_default import audit_source


def test_mutable_default_audit_allows_immutable_defaults():
    assert audit_source("def build(value=None, size=3):\n    return value\n") == []


def test_mutable_default_audit_reports_collection_literals():
    failures = audit_source("def one(items=[]):\n    pass\n\ndef two(*, options={}):\n    pass\n")
    assert failures == [
        "mutable default in one on line 1",
        "mutable default in two on line 4",
    ]
