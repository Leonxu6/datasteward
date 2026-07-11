"""指标查询工具（治理内核版）：query_metric / list_metrics。

口径唯一：编译自 ontology/metrics.yaml，智能体不再自己猜 SQL。
治理同权：required_markings ⊆ 用户有效 Marking（PBAC 目的约束同步生效），
          拒绝走 authorizationCheck/deny 审计——与 run_sql 同一套治理语义。
"""
import json
import time

from dm.ontology.metrics import compile_metric, metric_catalog, load_metrics
from dm.security import effective_user_markings
from dm.tools.audit import audit_event
from dm.tools.principal import Principal
from dm.warehouse.store import connect_ro


def list_metrics(principal: Principal) -> str:
    """列出全部业务指标定义（名称/中文名/口径说明/允许维度/单位/负责人）。回答口径类问题先看这里。"""
    t0 = time.time()
    cat = metric_catalog()
    audit_event(principal, "list_metrics", {}, "", ["metrics_registry"], len(cat), t0, True)
    return json.dumps(cat, ensure_ascii=False, indent=2)


def query_metric(principal: Principal, metric: str, dimensions: str = "",
                 filters: str = "", limit: int = 100) -> str:
    """按注册口径查询业务指标数值（缺料物料数/净需求/可发货量/库存总量/采购在途量/销售额）。
    参数：metric 指标名（先用 list_metrics 查可用项）；dimensions 逗号分隔的分组维度（可空）；
    filters 分号分隔的过滤（形如 material_id='M0001'；只接受简单比较）；limit 行数上限。
    返回 JSON：{metric, cn, sql, columns, rows}。涉敏指标受 Marking/PBAC 约束，无权会被拒。"""
    t0 = time.time()
    dims = [d for d in (dimensions or "").split(",") if d.strip()]
    flts = [f for f in (filters or "").split(";") if f.strip()]
    try:
        sql, mdef = compile_metric(metric, dims, flts, limit)
    except ValueError as e:
        audit_event(principal, "query_metric", {"metric": metric, "dimensions": dimensions,
                    "filters": filters}, "", [], 0, t0, False, str(e))
        return f"ERROR: {e}"
    # PBAC：指标级 Marking 门禁（与列级同一套有效 Marking 判定，目的约束天然生效）
    need = set(mdef.get("required_markings", []))
    um = effective_user_markings(principal.to_user())
    if not need <= um:
        miss = sorted(need - um)
        audit_event(principal, "query_metric", {"metric": metric}, sql, [mdef["base_model"]], 0, t0,
                    True, category="authorizationCheck", decision="deny", markings=miss)
        return (f"⛔ 权限不足：指标『{mdef.get('cn', metric)}』需要 Marking {miss}"
                f"（角色 {principal.role}" + (f"/目的『{principal.purpose}』" if principal.purpose else "")
                + "）。请如实告知用户该指标受权限保护，切勿臆造数值。")
    try:
        con = connect_ro()
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        con.close()
        out = {"metric": metric, "cn": mdef.get("cn", ""), "unit": mdef.get("unit", ""),
               "description": mdef.get("description", ""), "sql": sql, "columns": cols,
               "rows": [dict(zip(cols, r)) for r in rows]}
        audit_event(principal, "query_metric", {"metric": metric, "dimensions": dimensions,
                    "filters": filters}, sql, [mdef["base_model"]], len(rows), t0, True)
        return json.dumps(out, ensure_ascii=False, default=str, indent=2)
    except Exception as e:  # noqa: BLE001
        audit_event(principal, "query_metric", {"metric": metric}, sql, [mdef["base_model"]], 0, t0,
                    False, str(e))
        return f"ERROR: 指标查询失败: {e}"


def metric_names() -> list:
    return list(load_metrics().keys())
