from scripts.audit_debug_calls import audit_source


def test_debug_call_audit_allows_regular_calls():
    assert audit_source("logger.info('ready')\n") == []


def test_debug_call_audit_reports_breakpoint_and_pdb():
    failures = audit_source("breakpoint()\npdb.set_trace()\n")
    assert failures == [
        "breakpoint() on line 1",
        "pdb.set_trace() on line 2",
    ]
