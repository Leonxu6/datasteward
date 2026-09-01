from scripts.audit_sys_trace import audit_source


def test_sys_trace_audit_allows_gettrace():
    assert audit_source("sys.gettrace()\n") == []


def test_sys_trace_audit_reports_trace_installation():
    assert audit_source("sys.settrace(trace)\n") == ["sys.settrace() installs a runtime tracing hook on line 1"]
