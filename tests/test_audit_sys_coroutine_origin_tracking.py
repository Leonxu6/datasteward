from scripts.audit_sys_coroutine_origin_tracking import audit_source


def test_coroutine_origin_audit_allows_depth_lookup():
    assert audit_source("sys.get_coroutine_origin_tracking_depth()\n") == []


def test_coroutine_origin_audit_reports_depth_mutation():
    assert audit_source("sys.set_coroutine_origin_tracking_depth(10)\n") == ["sys.set_coroutine_origin_tracking_depth() mutates process diagnostics on line 1"]
