"""知识图谱查询工具（治理内核版）：Neo4j 实体关系层。

同步版给进程内 LangGraph 用；异步版给 stdio MCP 壳用。
"""
import json
import time

from dm.tools._isolation import arun_isolated, run_isolated
from dm.tools.audit import audit_event
from dm.tools.principal import Principal

_TIMEOUT = 45


def _argv(mode, entity_id, target_type, max_hops, cypher, limit):
    args = {"entity_id": entity_id, "target_type": target_type, "max_hops": max_hops,
            "cypher": cypher, "limit": limit}
    return [mode, json.dumps(args, ensure_ascii=False)]


def graph_query(principal: Principal, mode: str, entity_id: str = "", target_type: str = "",
                max_hops: int = 3, cypher: str = "", limit: int = 30) -> str:
    """知识图谱查询（find_related / impact_path / cypher 三种 mode）。"""
    t0 = time.time()
    try:
        res = run_isolated("dm.kg.graph_cli", _argv(mode, entity_id, target_type, max_hops, cypher, limit), _TIMEOUT)
        audit_event(principal, "graph_query",
                    {"mode": mode, "entity_id": entity_id, "target_type": target_type},
                    "", ["neo4j"], res.get("count", 0), t0, True)
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        audit_event(principal, "graph_query", {"mode": mode, "entity_id": entity_id}, "", [], 0, t0, False, str(e))
        return f"ERROR: 图查询失败: {e}"


async def agraph_query(principal: Principal, mode: str, entity_id: str = "", target_type: str = "",
                       max_hops: int = 3, cypher: str = "", limit: int = 30) -> str:
    """graph_query 的异步版（FastMCP 壳专用）。"""
    t0 = time.time()
    try:
        res = await arun_isolated("dm.kg.graph_cli", _argv(mode, entity_id, target_type, max_hops, cypher, limit), _TIMEOUT)
        audit_event(principal, "graph_query",
                    {"mode": mode, "entity_id": entity_id, "target_type": target_type},
                    "", ["neo4j"], res.get("count", 0), t0, True)
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        audit_event(principal, "graph_query", {"mode": mode, "entity_id": entity_id}, "", [], 0, t0, False, str(e))
        return f"ERROR: 图查询失败: {e}"
