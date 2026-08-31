import asyncio
import json
from unittest.mock import AsyncMock, patch

from dm.tools.graph import agraph_query, graph_query
from dm.tools.principal import Principal


def test_sync_query_preserves_data_when_audit_storage_fails():
    principal = Principal(user="alice", role="仓管")
    with patch("dm.tools.graph.run_isolated", return_value={"count": 1, "rows": [{"id": "M1"}]}), patch(
        "dm.tools.graph.audit_event", side_effect=RuntimeError("disk full")
    ):
        result = json.loads(graph_query(principal, "find_related", entity_id="M1"))
    assert result["count"] == 1
    assert result["rows"] == [{"id": "M1"}]
    assert result["audit_ok"] is False


def test_async_query_preserves_data_when_audit_storage_fails():
    principal = Principal(user="alice", role="仓管")
    with patch("dm.tools.graph.arun_isolated", new=AsyncMock(return_value={"count": 0, "rows": []})), patch(
        "dm.tools.graph.audit_event", side_effect=RuntimeError("disk full")
    ):
        result = json.loads(asyncio.run(agraph_query(principal, "find_related", entity_id="M1")))
    assert result["count"] == 0
    assert result["audit_ok"] is False


def test_worker_failure_remains_stable_when_error_audit_also_fails():
    principal = Principal(user="alice", role="仓管")
    with patch("dm.tools.graph.run_isolated", side_effect=RuntimeError("worker failed")), patch(
        "dm.tools.graph.audit_event", side_effect=RuntimeError("audit failed")
    ):
        assert graph_query(principal, "find_related", entity_id="M1") == "ERROR: 图查询失败"
