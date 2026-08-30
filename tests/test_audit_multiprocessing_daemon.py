from scripts.audit_multiprocessing_daemon import audit_source


def test_process_audit_allows_explicit_daemon_policy():
    assert audit_source("multiprocessing.Process(target=worker, daemon=False)\n") == []


def test_process_audit_reports_implicit_daemon_policy():
    assert audit_source("multiprocessing.Process(target=worker)\n") == ["multiprocessing.Process() without explicit daemon policy on line 1"]
