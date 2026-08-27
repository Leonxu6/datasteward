from scripts.audit_async_subprocess import audit_source


def test_async_subprocess_audit_allows_sync_function_subprocesses():
    assert audit_source("def work():\n    subprocess.run(['tool'], timeout=5)\n") == []


def test_async_subprocess_audit_reports_blocking_process_calls():
    assert audit_source("async def work():\n    subprocess.run(['tool'], timeout=5)\n") == [
        "subprocess.run() inside async function work on line 2"
    ]
