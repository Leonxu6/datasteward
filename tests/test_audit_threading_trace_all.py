from scripts.audit_threading_trace_all import audit_source


def test_thread_trace_audit_allows_trace_lookup():
    assert audit_source("threading.gettrace()\n") == []


def test_thread_trace_audit_reports_global_trace_installation():
    assert audit_source("threading.settrace_all_threads(trace)\n") == ["threading.settrace_all_threads() mutates global tracing behavior on line 1"]
