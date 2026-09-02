from scripts.audit_marshal_load import audit_source

def test_marshal_audit_ignores_serialization():
    assert audit_source("marshal.dumps(value)\n") == []

def test_marshal_audit_reports_deserialization():
    assert audit_source("marshal.loads(payload)\n") == ["marshal.loads deserializes marshal data on line 1"]