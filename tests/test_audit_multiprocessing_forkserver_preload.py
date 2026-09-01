from scripts.audit_multiprocessing_forkserver_preload import audit_source


def test_forkserver_preload_audit_allows_module_imports():
    assert audit_source("import worker\n") == []


def test_forkserver_preload_audit_reports_global_preloads():
    assert audit_source("multiprocessing.set_forkserver_preload(['worker'])\n") == ["multiprocessing.set_forkserver_preload() mutates child import policy on line 1"]
