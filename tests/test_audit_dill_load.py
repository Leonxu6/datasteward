from scripts.audit_dill_load import audit_source

def test_dill_audit_ignores_serialization():
    assert audit_source("dill.dumps(value)\n") == []

def test_dill_audit_reports_deserialization():
    assert audit_source("dill.loads(payload)\n") == ["dill.loads deserializes executable Python objects on line 1"]
