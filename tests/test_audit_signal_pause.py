from scripts.audit_signal_pause import audit_source

def test_signal_pause_ignores_other_signal_calls():
    assert audit_source("signal.raise_signal(signal.SIGUSR1)\n") == []

def test_signal_pause_reports_indefinite_wait():
    assert audit_source("signal.pause()\n") == ["signal.pause can block indefinitely on line 1"]