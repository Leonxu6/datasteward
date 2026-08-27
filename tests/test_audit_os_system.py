from scripts.audit_os_system import audit_source


def test_os_system_audit_allows_subprocess_lists():
    assert audit_source("subprocess.run(['tool'], timeout=5)\n") == []


def test_os_system_audit_reports_system_and_popen():
    failures = audit_source("os.system('echo hi')\nos.popen('echo hi')\n")
    assert failures == [
        "os.system() command execution on line 1",
        "os.popen() command execution on line 2",
    ]
