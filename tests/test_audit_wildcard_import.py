from scripts.audit_wildcard_import import audit_source


def test_wildcard_import_audit_allows_explicit_symbols():
    assert audit_source("from pathlib import Path\n") == []


def test_wildcard_import_audit_reports_star_imports():
    assert audit_source("from package import *\n") == [
        "wildcard import from package on line 1"
    ]
