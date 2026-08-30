from scripts.audit_signal_timers import audit_source


def test_signal_timer_audit_allows_reads():
    assert audit_source("signal.getsignal(signal.SIGTERM)\n") == []


def test_signal_timer_audit_reports_alarm():
    assert audit_source("signal.alarm(5)\n") == ["signal.alarm() mutates process timers on line 1"]
