from scripts.audit_unbounded_queue import audit_source


def test_queue_audit_allows_capacity():
    assert audit_source("queue.Queue(maxsize=100)\n") == []


def test_queue_audit_reports_implicit_capacity():
    assert audit_source("asyncio.Queue()\n") == ["unbounded asyncio.Queue() on line 1"]
