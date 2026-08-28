from scripts.audit_signal_handlers import audit_source


def test_signal_audit_allows_event_objects():
    assert audit_source("stop_event.set()\n") == []


def test_signal_audit_reports_process_handler_mutation():
    assert audit_source("signal.signal(signal.SIGTERM, handler)\n") == [
        "signal.signal() mutates process-wide handlers on line 1"
    ]
