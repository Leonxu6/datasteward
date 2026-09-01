from scripts.audit_sys_asyncgen_hooks import audit_source


def test_asyncgen_hook_audit_allows_hook_lookup():
    assert audit_source("sys.get_asyncgen_hooks()\n") == []


def test_asyncgen_hook_audit_reports_hook_mutation():
    assert audit_source("sys.set_asyncgen_hooks(firstiter=first, finalizer=last)\n") == ["sys.set_asyncgen_hooks() mutates process async-generator behavior on line 1"]
