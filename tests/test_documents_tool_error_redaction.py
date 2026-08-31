import asyncio
from unittest.mock import AsyncMock, patch

from dm.tools.documents import asearch_documents, search_documents
from dm.tools.principal import Principal


def test_sync_search_does_not_expose_worker_exception_details():
    principal = Principal(user="alice", role="仓管")
    with patch(
        "dm.tools.documents.run_isolated", side_effect=RuntimeError("postgres://user:secret@vector-db")
    ), patch("dm.tools.documents.audit_event") as audit:
        response = search_documents(principal, "query")
    assert response == "ERROR: 文档检索失败"
    assert "secret" not in response
    assert audit.call_args.args[8] == "RuntimeError"


def test_async_search_does_not_expose_worker_exception_details():
    principal = Principal(user="alice", role="仓管")
    with patch(
        "dm.tools.documents.arun_isolated", new=AsyncMock(side_effect=RuntimeError("token=secret"))
    ), patch("dm.tools.documents.audit_event") as audit:
        response = asyncio.run(asearch_documents(principal, "query"))
    assert response == "ERROR: 文档检索失败"
    assert audit.call_args.args[8] == "RuntimeError"
