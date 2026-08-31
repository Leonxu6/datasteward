import asyncio
from unittest.mock import AsyncMock, patch

from dm.tools.graph import agraph_query, graph_query
from dm.tools.principal import Principal


def test_sync_graph_errors_do_not_expose_worker_details():
    principal = Principal(user="alice", role="仓管")
    with patch(
        "dm.tools.graph.run_isolated", side_effect=RuntimeError("neo4j://user:secret@internal")
    ), patch("dm.tools.graph.audit_event") as audit:
        response = graph_query(principal, "find_related", entity_id="M1")
    assert response == "ERROR: 图查询失败"
    assert "secret" not in response
    assert audit.call_args.args[8] == "RuntimeError"


def test_async_graph_errors_do_not_expose_worker_details():
    principal = Principal(user="alice", role="仓管")
    with patch(
        "dm.tools.graph.arun_isolated",
        new=AsyncMock(side_effect=RuntimeError("token=secret")),
    ), patch("dm.tools.graph.audit_event") as audit:
        response = asyncio.run(agraph_query(principal, "find_related", entity_id="M1"))
    assert response == "ERROR: 图查询失败"
    assert audit.call_args.args[8] == "RuntimeError"
