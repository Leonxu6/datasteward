from scripts.audit_tzset import audit_source


def test_tzset_audit_allows_localtime_reads():
    assert audit_source("time.localtime()\n") == []


def test_tzset_audit_reports_process_mutation():
    assert audit_source("time.tzset()\n") == ["time.tzset() mutates process timezone on line 1"]
