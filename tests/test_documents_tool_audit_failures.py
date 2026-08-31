import asyncio
import json
from unittest.mock import AsyncMock, patch

from dm.tools.documents import asearch_documents, search_documents
from dm.tools.principal import Principal


def test_sync_search_preserves_hits_when_audit_storage_fails():
    principal = Principal(user="alice", role="仓管")
    with patch("dm.tools.documents.run_isolated", return_value=[{"doc_id": "D1", "content": "text"}]), patch(
        "dm.tools.documents.audit_event", side_effect=RuntimeError("disk full")
    ):
        result = json.loads(search_documents(principal, "query"))
    assert result[0]["doc_id"] == "D1"
    assert result[0]["audit_warning"] == "search completed but audit persistence failed"


def test_async_search_preserves_hits_when_audit_storage_fails():
    principal = Principal(user="alice", role="仓管")
    with patch(
        "dm.tools.documents.arun_isolated",
        new=AsyncMock(return_value=[{"doc_id": "D1", "content": "text"}]),
    ), patch("dm.tools.documents.audit_event", side_effect=RuntimeError("disk full")):
        result = json.loads(asyncio.run(asearch_documents(principal, "query")))
    assert result[0]["doc_id"] == "D1"
    assert "audit_warning" in result[0]


def test_worker_failure_stays_stable_when_error_audit_also_fails():
    principal = Principal(user="alice", role="仓管")
    with patch("dm.tools.documents.run_isolated", side_effect=RuntimeError("worker failed")), patch(
        "dm.tools.documents.audit_event", side_effect=RuntimeError("audit failed")
    ):
        assert search_documents(principal, "query") == "ERROR: 文档检索失败"
