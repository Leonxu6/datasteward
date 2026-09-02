from scripts.audit_subprocess_preexec_fn import audit_source

def test_preexec_audit_allows_default_subprocess():
    assert audit_source("subprocess.Popen(argv)\n") == []

def test_preexec_audit_reports_hook():
    assert audit_source("subprocess.Popen(argv, preexec_fn=setup)\n") == ["subprocess preexec_fn is unsafe in threaded services on line 1"]