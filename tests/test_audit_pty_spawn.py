from scripts.audit_pty_spawn import audit_source

def test_pty_spawn_ignores_terminal_helpers():
    assert audit_source("pty.openpty()\n") == []

def test_pty_spawn_reports_interactive_child():
    assert audit_source("pty.spawn(['/bin/sh'])\n") == ["pty.spawn launches an interactive child process on line 1"]
