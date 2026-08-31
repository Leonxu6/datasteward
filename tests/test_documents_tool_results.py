import asyncio
from unittest.mock import AsyncMock, patch

from dm.tools.documents import asearch_documents, search_documents
from dm.tools.principal import Principal


def test_sync_search_rejects_malformed_worker_results():
    principal = Principal(user="alice", role="仓管")
    invalid = (None, {}, "hits", ["not-an-object"], [{"id": 1}, {"id": 2}])
    for result in invalid:
        top_k = 1 if isinstance(result, list) and len(result) > 1 else 5
        with patch("dm.tools.documents.run_isolated", return_value=result), patch("dm.tools.documents.audit_event") as audit:
            response = search_documents(principal, "query", top_k)
        assert response.startswith("ERROR: 文档检索失败:")
        assert audit.call_args.args[7] is False


def test_async_search_rejects_non_list_worker_result():
    principal = Principal(user="alice", role="仓管")
    with patch("dm.tools.documents.arun_isolated", new=AsyncMock(return_value={"id": 1})), patch(
        "dm.tools.documents.audit_event"
    ) as audit:
        response = asyncio.run(asearch_documents(principal, "query", 5))
    assert response.startswith("ERROR: 文档检索失败:")
    assert audit.call_args.args[7] is False
