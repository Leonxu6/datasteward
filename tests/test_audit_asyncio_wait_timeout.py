from scripts.audit_asyncio_wait_timeout import audit_source

def test_asyncio_wait_allows_timeout():
    assert audit_source("asyncio.wait(tasks, timeout=1)\n") == []

def test_asyncio_wait_reports_missing_timeout():
    assert audit_source("asyncio.wait(tasks)\n") == ["asyncio.wait without timeout on line 1"]