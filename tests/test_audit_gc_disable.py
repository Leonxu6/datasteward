from scripts.audit_gc_disable import audit_source


def test_gc_audit_allows_targeted_collection():
    assert audit_source("gc.collect()\n") == []


def test_gc_audit_reports_global_disable():
    assert audit_source("gc.disable()\n") == [
        "gc.disable() disables cyclic collection process-wide on line 1"
    ]
