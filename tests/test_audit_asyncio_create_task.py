from scripts.audit_asyncio_create_task import audit_source


def test_task_audit_allows_named_tasks():
    assert audit_source("asyncio.create_task(worker(), name='sync-worker')\n") == []


def test_task_audit_reports_anonymous_tasks():
    assert audit_source("asyncio.create_task(worker())\n") == ["asyncio.create_task() without name on line 1"]
