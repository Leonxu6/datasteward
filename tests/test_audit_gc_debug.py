from scripts.audit_gc_debug import audit_source


def test_gc_debug_audit_allows_debug_lookup():
    assert audit_source("gc.get_debug()\n") == []


def test_gc_debug_audit_reports_global_debug_mutation():
    assert audit_source("gc.set_debug(gc.DEBUG_STATS)\n") == ["gc.set_debug() mutates process-wide GC diagnostics on line 1"]
