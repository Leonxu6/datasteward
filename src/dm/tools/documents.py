"""文档语义检索工具（治理内核版）：RAG 入口，pgvector + 本地嵌入。

同步版给进程内 LangGraph 用；异步版给 stdio MCP 壳用（asyncio 场景，见 _isolation 说明）。
两版共用同一审计与返回格式。
"""
import json
import time

from dm.tools._isolation import arun_isolated, run_isolated
from dm.tools.audit import audit_event
from dm.tools.principal import Principal

_TIMEOUT = 60
_MAX_QUERY_CHARS = 2000
_MAX_TOP_K = 100


def _query_text(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("query must be clean non-empty text")
    if len(value) > _MAX_QUERY_CHARS:
        raise ValueError(f"query must be at most {_MAX_QUERY_CHARS} characters")
    if any((ord(ch) < 32 and ch not in "\n\r\t") or ord(ch) == 127 for ch in value):
        raise ValueError("query contains unsafe control characters")
    return value


def _top_k(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("top_k must be an integer")
    if value < 1 or value > _MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {_MAX_TOP_K}")
    return value


def search_documents(principal: Principal, query: str, top_k: int = 5) -> str:
    """检索非结构化文档库（采购合同 / 作业指导书SOP / 进货检验质检报告 / 设备维护手册 / 物料技术规格书）。"""
    t0 = time.time()
    try:
        query = _query_text(query)
        top_k = _top_k(top_k)
        hits = run_isolated("dm.docs.search_cli", [query, str(top_k)], _TIMEOUT)
        audit_event(principal, "search_documents", {"query": query, "top_k": top_k}, "",
                    ["doc_chunk"], len(hits), t0, True)
        return json.dumps(hits, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        audit_event(principal, "search_documents", {"query": query, "top_k": top_k}, "", [], 0, t0, False, str(e))
        return f"ERROR: 文档检索失败: {e}"


async def asearch_documents(principal: Principal, query: str, top_k: int = 5) -> str:
    """search_documents 的异步版（FastMCP 壳专用）。"""
    t0 = time.time()
    try:
        query = _query_text(query)
        top_k = _top_k(top_k)
        hits = await arun_isolated("dm.docs.search_cli", [query, str(top_k)], _TIMEOUT)
        audit_event(principal, "search_documents", {"query": query, "top_k": top_k}, "",
                    ["doc_chunk"], len(hits), t0, True)
        return json.dumps(hits, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        audit_event(principal, "search_documents", {"query": query, "top_k": top_k}, "", [], 0, t0, False, str(e))
        return f"ERROR: 文档检索失败: {e}"
