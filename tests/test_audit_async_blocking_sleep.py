from scripts.audit_async_blocking_sleep import audit_source


def test_async_blocking_sleep_audit_allows_asyncio_sleep():
    assert audit_source("async def work():\n    await asyncio.sleep(1)\n") == []


def test_async_blocking_sleep_audit_reports_time_sleep():
    assert audit_source("async def work():\n    time.sleep(1)\n") == [
        "time.sleep() inside async function work on line 2"
    ]
