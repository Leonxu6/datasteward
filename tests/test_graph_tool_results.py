import asyncio
from unittest.mock import AsyncMock, patch

from dm.tools.graph import agraph_query, graph_query
from dm.tools.principal import Principal


def test_sync_graph_query_rejects_malformed_worker_results():
    principal = Principal(user="alice", role="仓管")
    invalid = (None, [], "ok", {"count": True}, {"count": -1}, {"count": "2"})
    for result in invalid:
        with patch("dm.tools.graph.run_isolated", return_value=result), patch("dm.tools.graph.audit_event") as audit:
            response = graph_query(principal, "find_related", entity_id="M1")
        assert response == "ERROR: 图查询失败"
        assert audit.call_args.args[7] is False


def test_async_graph_query_rejects_malformed_worker_results():
    principal = Principal(user="alice", role="仓管")
    with patch("dm.tools.graph.arun_isolated", new=AsyncMock(return_value={"count": -1})), patch(
        "dm.tools.graph.audit_event"
    ) as audit:
        response = asyncio.run(agraph_query(principal, "find_related", entity_id="M1"))
    assert response == "ERROR: 图查询失败"
    assert audit.call_args.args[7] is False
