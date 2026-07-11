"""结构化数仓三工具（治理内核版）：list_tables / describe_table / run_sql。

行为与原 mcp_server 完全一致（返回串、报错文案、审计字段逐字不变）——
唯一差别：身份从环境变量改为显式 Principal。PBAC/行列策略/脱敏依旧在 run_sql 入口强制。
"""
import json
import time

from dm.schema import TABLES, business_table_names, table_by_name
from dm.security import apply_mask, apply_row_policies, enforce_query
from dm.tools.audit import audit_event
from dm.tools.principal import Principal
from dm.tools.sql_guard import tables_in, validate_readonly
from dm.warehouse.store import connect_ro

MAX_ROWS = 200


def list_tables(principal: Principal) -> str:
    """列出数据仓库里所有业务表（表英文名、中文名、说明、行数）。建议先调用它了解有哪些数据。"""
    t0 = time.time()
    try:
        con = connect_ro()
        out = []
        for t in TABLES:
            n = con.execute(f'SELECT COUNT(*) FROM `{t["name"]}`').fetchone()[0]
            out.append({"table": t["name"], "cn": t["cn"], "desc": t["desc"], "rows": n})
        con.close()
        audit_event(principal, "list_tables", {}, "", [t["name"] for t in TABLES], len(out), t0, True)
        return json.dumps(out, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        audit_event(principal, "list_tables", {}, "", [], 0, t0, False, str(e))
        return f"ERROR: {e}"


def describe_table(principal: Principal, name: str) -> str:
    """查看某张表的字段定义：列名、类型、中文名、是否主键、外键指向。参数 name 为表英文名。"""
    t0 = time.time()
    t = table_by_name(name)
    if not t or name not in business_table_names():
        audit_event(principal, "describe_table", {"name": name}, "", [], 0, t0, False, "unknown table")
        return f"ERROR: 未知表 '{name}'。请用 list_tables 查看可用表。"
    pk = set(t["pk"].split("+"))
    fk = {f[0]: f[1] for f in t["fks"]}
    cols = [{"column": c[0], "type": c[1], "cn": c[2], "pk": c[0] in pk, "fk_to": fk.get(c[0])}
            for c in t["columns"]]
    audit_event(principal, "describe_table", {"name": name}, "", [name], len(cols), t0, True)
    return json.dumps({"table": name, "cn": t["cn"], "desc": t["desc"], "columns": cols},
                      ensure_ascii=False, indent=2)


def run_sql(principal: Principal, sql: str) -> str:
    """对数据仓库执行只读 SELECT 查询并返回结果（最多 200 行，JSON）。
    仅允许单条 SELECT / WITH 查询；任何写操作、DDL、多语句都会被拒绝。
    表结构请先用 list_tables / describe_table 获取。"""
    t0 = time.time()
    clean, guard_err = validate_readonly(sql)
    if guard_err:
        reason = {"ERROR: 只允许单条查询语句（不要用分号拼接多条）。": "multiple statements",
                  "ERROR: 只允许 SELECT/WITH 查询。": "not a select"}.get(guard_err, "forbidden keyword")
        audit_event(principal, "run_sql", {"sql": sql}, clean, [], 0, t0, False, reason)
        return guard_err
    tables = tables_in(clean)
    # 权限强制（Palantir 两层：强制 Markings AND 自主角色；行/列过滤）——在数据入口拦截
    user = principal.to_user()
    decision = enforce_query(user, clean, tables)
    if not decision["allow"]:
        audit_event(principal, "run_sql", {"sql": sql}, clean, tables, 0, t0, True,
                    category="authorizationCheck", decision="deny", markings=decision["hit_markings"])
        return ("⛔ 权限不足：" + decision["reason"] +
                "。请如实告知用户该数据受权限(Marking)保护、当前角色无权查看，切勿臆造数值。")
    exec_sql = apply_row_policies(user, clean, tables)   # 行级对象策略：收窄可见行
    try:
        con = connect_ro()
        cur = con.execute(exec_sql)
        colnames = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(MAX_ROWS)
        con.close()
        masked_rows, masked_cols = apply_mask(colnames, rows, decision["mask_columns"])
        result = [dict(zip(colnames, r)) for r in masked_rows]
        audit_event(principal, "run_sql", {"sql": sql}, clean, tables, len(result), t0, True,
                    category="dataQuery", decision="allow")
        out = {"columns": colnames, "row_count": len(result), "rows": result,
               "truncated": len(result) >= MAX_ROWS}
        notes = []
        if masked_cols:
            out["masked_columns"] = masked_cols
            notes.append("以下列因权限(Marking)被屏蔽为 null：" + ", ".join(masked_cols))
        if exec_sql != clean:
            out["row_policy_applied"] = True
            notes.append("已按行级权限策略收窄可见行（仅授权范围内数据）")
        if notes:
            out["notice"] = "；".join(notes) + "。如用户问及，请说明数据受权限保护，勿臆造。"
        return json.dumps(out, ensure_ascii=False, default=str, indent=2)
    except Exception as e:  # noqa: BLE001
        audit_event(principal, "run_sql", {"sql": sql}, clean, tables, 0, t0, False, str(e))
        return f"ERROR: 查询失败: {e}"
