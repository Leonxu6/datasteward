from scripts.audit_asyncio_run import audit_source


def test_asyncio_run_audit_allows_awaited_coroutines():
    assert audit_source("async def f():\n    await worker()\n") == []


def test_asyncio_run_audit_reports_loop_ownership():
    assert audit_source("asyncio.run(worker())\n") == [
        "asyncio.run() owns the event loop on line 1; keep it at an explicit process entry point"
    ]
