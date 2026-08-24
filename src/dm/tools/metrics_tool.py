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


def _query_text(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    if value != value.strip():
        raise ValueError(f"{field} must not have leading or trailing whitespace")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field} contains control characters")
    return value


def _close_quietly(resource) -> None:
    if resource is None:
        return
    try:
        resource.close()
    except Exception:  # noqa: BLE001
        pass


def _rows_to_records(columns: list, rows: list) -> list[dict]:
    if any(not isinstance(col, str) or not col for col in columns):
        raise ValueError("metric query columns must be non-empty strings")
    if len(set(columns)) != len(columns):
        raise ValueError("metric query returned duplicate column names")
    records: list[dict] = []
    for row in rows:
        try:
            width = len(row)
        except TypeError as exc:
            raise ValueError("metric query rows must be sized sequences") from exc
        if width != len(columns):
            raise ValueError("metric query row length does not match cursor columns")
        records.append(dict(zip(columns, row)))
    return records


def list_metrics(principal: Principal) -> str:
    t0 = time.time()
    cat = metric_catalog()
    audit_event(principal, "list_metrics", {}, "", ["metrics_registry"], len(cat), t0, True)
    return json.dumps(cat, ensure_ascii=False, indent=2)


def query_metric(principal: Principal, metric: str, dimensions: str = "",
                 filters: str = "", limit: int = 100) -> str:
    t0 = time.time()
    try:
        dimensions = _query_text(dimensions, field="dimensions")
        filters = _query_text(filters, field="filters")
        dims = [d for d in dimensions.split(",") if d.strip()]
        flts = [f for f in filters.split(";") if f.strip()]
        sql, mdef = compile_metric(metric, dims, flts, limit)
    except ValueError as e:
        audit_event(principal, "query_metric", {"metric": metric, "dimensions": dimensions,
                    "filters": filters}, "", [], 0, t0, False, str(e))
        return f"ERROR: {e}"
    need = set(mdef.get("required_markings", []))
    um = effective_user_markings(principal.to_user())
    if not need <= um:
        miss = sorted(need - um)
        audit_event(principal, "query_metric", {"metric": metric}, sql, [mdef["base_model"]], 0, t0,
                    True, category="authorizationCheck", decision="deny", markings=miss)
        return (f"⛔ 权限不足：指标『{mdef.get('cn', metric)}』需要 Marking {miss}"
                f"（角色 {principal.role}" + (f"/目的『{principal.purpose}』" if principal.purpose else "")
                + "）。请如实告知用户该指标受权限保护，切勿臆造数值。")
    con = None
    cur = None
    try:
        con = connect_ro()
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        records = _rows_to_records(cols, rows)
        out = {"metric": metric, "cn": mdef.get("cn", ""), "unit": mdef.get("unit", ""),
               "description": mdef.get("description", ""), "sql": sql, "columns": cols,
               "rows": records}
        audit_event(principal, "query_metric", {"metric": metric, "dimensions": dimensions,
                    "filters": filters}, sql, [mdef["base_model"]], len(rows), t0, True)
        return json.dumps(out, ensure_ascii=False, default=str, indent=2)
    except Exception as e:  # noqa: BLE001
        audit_event(principal, "query_metric", {"metric": metric}, sql, [mdef["base_model"]], 0, t0,
                    False, str(e))
        return f"ERROR: 指标查询失败: {e}"
    finally:
        _close_quietly(cur)
        _close_quietly(con)


def metric_names() -> list:
    return list(load_metrics().keys())
