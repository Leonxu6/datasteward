"""审计写入（治理内核版）。

每次工具调用（allow/deny/error）落一条 audit_log JSONL。序列化和耗时字段采用
防御式 helper，避免 Decimal/datetime/递归参数或系统时钟回拨让审计本身失败。
"""
import time
from datetime import datetime, timezone

from dm.tools.audit_record import elapsed_ms, join_labels, safe_json
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
            "session_id": principal.session_id,
            "channel": principal.channel,
            "category": category,
            "decision": decision,
            "user": principal.user,
            "role": principal.role,
            "purpose": principal.purpose,
            "tool_name": str(tool),
            "tool_args": safe_json(args),
            "sql": str(sql or ""),
            "tables_touched": join_labels(tables),
            "markings": join_labels(markings),
            "row_count": rowcount,
            "duration_ms": elapsed_ms(t0, time.time()),
            "ok": bool(ok),
            "error": str(error or ""),
        },
    )
