from scripts.audit_uuid1 import audit_source


def test_uuid1_audit_allows_random_uuid_generation():
    assert audit_source("import uuid\nidentifier = uuid.uuid4()\n") == []


def test_uuid1_audit_reports_host_derived_uuid():
    assert audit_source("import uuid\nidentifier = uuid.uuid1()\n") == [
        "uuid.uuid1() call on line 2; prefer non-host-derived identifiers"
    ]
