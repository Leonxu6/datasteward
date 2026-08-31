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


def _validated_result(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("graph worker returned a malformed result")
    count = value.get("count", 0)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("graph worker count must be a non-negative integer")
    return value


def _error_category(exc: BaseException) -> str:
    name = type(exc).__name__
    return name if name and len(name) <= 100 else "GraphQueryError"


def _audit_error(principal: Principal, mode: str, entity_id: str, t0: float, exc: BaseException) -> None:
    try:
        audit_event(
            principal, "graph_query", {"mode": mode, "entity_id": entity_id}, "", [], 0, t0, False,
            _error_category(exc),
        )
    except Exception:  # noqa: BLE001
        return


def _audit_success(principal: Principal, mode: str, entity_id: str, target_type: str, t0: float, res: dict) -> dict:
    try:
        audit_event(
            principal, "graph_query", {"mode": mode, "entity_id": entity_id, "target_type": target_type},
            "", ["neo4j"], res.get("count", 0), t0, True,
        )
        return res
    except Exception:  # noqa: BLE001
        copy = dict(res)
        copy["audit_ok"] = False
        copy["audit_warning"] = "query completed but audit persistence failed"
        return copy


def graph_query(principal: Principal, mode: str, entity_id: str = "", target_type: str = "",
                max_hops: int = 3, cypher: str = "", limit: int = 30) -> str:
    """知识图谱查询（find_related / impact_path / cypher 三种 mode）。"""
    t0 = time.time()
    try:
        res = _validated_result(
            run_isolated("dm.kg.graph_cli", _argv(mode, entity_id, target_type, max_hops, cypher, limit), _TIMEOUT)
        )
    except Exception as exc:  # noqa: BLE001
        _audit_error(principal, mode, entity_id, t0, exc)
        return "ERROR: 图查询失败"
    return json.dumps(_audit_success(principal, mode, entity_id, target_type, t0, res), ensure_ascii=False, indent=2)


async def agraph_query(principal: Principal, mode: str, entity_id: str = "", target_type: str = "",
                       max_hops: int = 3, cypher: str = "", limit: int = 30) -> str:
    """graph_query 的异步版（FastMCP 壳专用）。"""
    t0 = time.time()
    try:
        res = _validated_result(
            await arun_isolated("dm.kg.graph_cli", _argv(mode, entity_id, target_type, max_hops, cypher, limit), _TIMEOUT)
        )
    except Exception as exc:  # noqa: BLE001
        _audit_error(principal, mode, entity_id, t0, exc)
        return "ERROR: 图查询失败"
    return json.dumps(_audit_success(principal, mode, entity_id, target_type, t0, res), ensure_ascii=False, indent=2)
