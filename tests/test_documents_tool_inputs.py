import asyncio
from unittest.mock import AsyncMock, patch

from dm.tools.documents import asearch_documents, search_documents
from dm.tools.principal import Principal


def test_sync_search_rejects_invalid_inputs_before_worker_launch():
    principal = Principal(user="alice", role="仓管")
    cases = (
        (None, 5),
        ("", 5),
        (" padded", 5),
        ("bad\x00query", 5),
        ("q" * 2001, 5),
        ("query", True),
        ("query", 0),
        ("query", 101),
        ("query", 2.5),
    )
    for query, top_k in cases:
        with patch("dm.tools.documents.run_isolated") as worker, patch("dm.tools.documents.audit_event"):
            response = search_documents(principal, query, top_k)  # type: ignore[arg-type]
        assert response == "ERROR: 文档检索失败"
        worker.assert_not_called()


def test_async_search_rejects_invalid_top_k_before_worker_launch():
    principal = Principal(user="alice", role="仓管")
    worker = AsyncMock()
    with patch("dm.tools.documents.arun_isolated", new=worker), patch("dm.tools.documents.audit_event"):
        response = asyncio.run(asearch_documents(principal, "query", True))  # type: ignore[arg-type]
    assert response == "ERROR: 文档检索失败"
    worker.assert_not_awaited()
