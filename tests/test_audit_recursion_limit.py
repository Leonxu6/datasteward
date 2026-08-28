from scripts.audit_recursion_limit import audit_source


def test_recursion_limit_audit_allows_iterative_code():
    assert audit_source("result = list(items)\n") == []


def test_recursion_limit_audit_reports_global_mutation():
    assert audit_source("sys.setrecursionlimit(10000)\n") == [
        "sys.setrecursionlimit() mutates interpreter-wide state on line 1"
    ]
