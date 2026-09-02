from scripts.audit_cloudpickle_load import audit_source

def test_cloudpickle_audit_ignores_serialization():
    assert audit_source("cloudpickle.dumps(value)\n") == []

def test_cloudpickle_audit_reports_deserialization():
    assert audit_source("cloudpickle.loads(payload)\n") == ["cloudpickle.loads deserializes executable Python objects on line 1"]