from scripts.audit_resource_limits import audit_source


def test_resource_audit_allows_limit_reads():
    assert audit_source("resource.getrlimit(resource.RLIMIT_NOFILE)\n") == []


def test_resource_audit_reports_limit_mutation():
    assert audit_source("resource.setrlimit(resource.RLIMIT_NOFILE, limits)\n") == ["resource.setrlimit() mutates process limits on line 1"]
