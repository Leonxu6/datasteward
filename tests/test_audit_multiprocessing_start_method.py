from scripts.audit_multiprocessing_start_method import audit_source


def test_start_method_audit_allows_process_creation():
    assert audit_source("multiprocessing.Process(target=work)\n") == []


def test_start_method_audit_reports_global_policy_changes():
    assert audit_source("multiprocessing.set_start_method('spawn')\n") == ["multiprocessing.set_start_method() mutates process policy on line 1"]
