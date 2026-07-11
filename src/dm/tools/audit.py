"""审计写入（治理内核版）：字段与原 mcp_server._audit 逐字一致，身份来自 Principal。

每次工具调用（无论 allow/deny/error）都落一条 logs/audit_log.jsonl，
category/decision 对标 Palantir 审计分类与授权决策；session_id 与任务链同键关联。
"""
import json
import time
from datetime import datetime

from dm.tools.principal import Principal
from dm.warehouse.store import append_log


def audit_event(principal: Principal, tool, args, sql, tables, rowcount, t0, ok, error="",
                category="dataQuery", decision="allow", markings=None):
    """写一条审计。JSONL 字段名与顺序保持与旧版完全一致（管理平台/回放依赖）。"""
    now = datetime.now()
    append_log("audit_log", {
        "audit_id": "A" + now.strftime("%Y%m%d%H%M%S%f"),
        "ts": now.isoformat(timespec="seconds"),
        "session_id": principal.session_id,
        "channel": principal.channel,
        "category": category,          # dataQuery / authorizationCheck / actionExecute / dataImport ...
        "decision": decision,          # allow / deny
        "user": principal.user,
        "role": principal.role,
        "purpose": principal.purpose,
        "tool_name": tool,
        "tool_args": json.dumps(args, ensure_ascii=False),
        "sql": sql,
        "tables_touched": ",".join(tables),
        "markings": ",".join(markings) if markings else "",
        "row_count": rowcount,
        "duration_ms": int((time.time() - t0) * 1000),
        "ok": ok,
        "error": error,
    })
