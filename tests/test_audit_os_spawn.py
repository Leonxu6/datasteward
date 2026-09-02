from scripts.audit_os_spawn import audit_source

def test_os_spawn_ignores_managed_subprocess_calls():
    assert audit_source("subprocess.run(argv, check=True)\n") == []

def test_os_spawn_reports_legacy_spawn():
    assert audit_source("os.spawnv(os.P_WAIT, path, argv)\n") == ["os.spawnv bypasses the managed subprocess policy on line 1"]
