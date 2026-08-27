from scripts.audit_sys_path_mutation import audit_source


def test_sys_path_audit_allows_regular_path_reads():
    assert audit_source("import sys\npaths = list(sys.path)\n") == []


def test_sys_path_audit_reports_runtime_mutation():
    assert audit_source("import sys\nsys.path.insert(0, '/tmp/plugins')\n") == [
        "sys.path.insert() mutation on line 2"
    ]
