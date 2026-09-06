"""审计写入（治理内核版）。

每次工具调用（allow/deny/error）落一条 audit_log JSONL。序列化和耗时字段采用
防御式 helper，避免 Decimal/datetime/递归参数或系统时钟回拨让审计本身失败。
"""
import time
from datetime import datetime, timezone

from dm.tools.audit_record import elapsed_ms, join_labels, safe_json, safe_text
from dm.tools.principal import Principal
from dm.warehouse.store import append_log


def audit_event(
    principal: Principal,
    tool,
    args,
    sql,
    tables,
    rowcount,
    t0,
    ok,
    error="",
    category="dataQuery",
    decision="allow",
    markings=None,
):
    """写一条审计，字段契约保持与管理平台/回放页兼容。"""
    now = datetime.now(timezone.utc)
    append_log(
        "audit_log",
        {
            "audit_id": "A" + now.strftime("%Y%m%d%H%M%S%f"),
            "ts": now.isoformat(timespec="seconds"),
            "session_id": safe_text(principal.session_id, limit=500),
            "channel": safe_text(principal.channel, limit=200),
            "category": safe_text(category, limit=200),
            "decision": safe_text(decision, limit=200),
            "user": safe_text(principal.user, limit=500),
            "role": safe_text(principal.role, limit=500),
            "purpose": safe_text(principal.purpose, limit=1000),
            "tool_name": safe_text(tool, limit=500),
            "tool_args": safe_json(args),
            "sql": safe_text(sql, limit=10_000),
            "tables_touched": join_labels(tables),
            "markings": join_labels(markings),
            "row_count": rowcount,
            "duration_ms": elapsed_ms(t0, time.time()),
            "ok": bool(ok),
            "error": safe_text(error, limit=10_000),
        },
    )
