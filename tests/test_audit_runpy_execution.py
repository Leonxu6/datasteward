from scripts.audit_runpy_execution import audit_source

def test_runpy_audit_ignores_imports():
    assert audit_source("importlib.import_module(name)\n") == []

def test_runpy_audit_reports_dynamic_execution():
    assert audit_source("runpy.run_path(path)\n") == ["runpy.run_path dynamically executes Python code on line 1"]