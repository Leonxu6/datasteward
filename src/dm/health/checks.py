"""数据健康监控（对标 Palantir Data Health / Foundry Rules）。"""
from datetime import datetime

from dm.config import SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD, SRC_PG_PORT, SRC_PG_USER
from dm.schema import business_table_names, table_by_name
from dm.warehouse.store import connect_ro

CHECK_CATALOG = [
    {"id": "volume_all", "type": "volume", "min_rows": 1, "severity": "error", "desc": "所有业务表应非空（缺数据探测）"},
    {"id": "expect_inventory_qty", "type": "expectation", "table": "inventory", "predicate": "qty < 0", "severity": "error", "desc": "库存数量不应为负"},
    {"id": "expect_safety_stock", "type": "expectation", "table": "material", "predicate": "safety_stock < 0", "severity": "error", "desc": "安全库存阈值不应为负"},
    {"id": "expect_so_qty", "type": "expectation", "table": "sales_order", "predicate": "qty <= 0", "severity": "warn", "desc": "销售订单数量应为正"},
    {"id": "parity_inventory", "type": "parity", "table": "inventory", "severity": "error", "desc": "库存 源(PG)↔汇(StarRocks) 行数对账（CDC 健康）"},
    {"id": "parity_material", "type": "parity", "table": "material", "severity": "error", "desc": "物料 源↔汇 行数对账"},
    {"id": "parity_sales_order", "type": "parity", "table": "sales_order", "severity": "error", "desc": "销售订单 源↔汇 行数对账"},
    {"id": "parity_purchase_order", "type": "parity", "table": "purchase_order", "severity": "error", "desc": "采购单 源↔汇 行数对账"},
    {"id": "schema_inventory", "type": "schema", "table": "inventory", "severity": "warn", "desc": "库存表结构一致（无列漂移）"},
    {"id": "freshness_inventory", "type": "freshness", "table": "inventory", "column": "update_time", "max_age_days": 30, "severity": "warn", "desc": "库存数据新鲜度（最新更新距今）"},
    {"id": "dbt_tests", "type": "dbt", "severity": "error", "desc": "dbt 质量测试（唯一/非空/引用完整/业务规则）全部通过"},
]


def _sr_scalar(sql):
    con = connect_ro()
    try:
        row = con.execute(sql).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def _sr_cols(table):
    con = connect_ro()
    try:
        cur = con.execute(f"SELECT * FROM `{table}` LIMIT 0")
        return [d[0] for d in cur.description]
    finally:
        con.close()


def _pg_scalar(sql):
    import psycopg
    with psycopg.connect(host=SRC_PG_HOST, port=SRC_PG_PORT, user=SRC_PG_USER,
                         password=SRC_PG_PASSWORD, dbname=SRC_PG_DB, connect_timeout=15) as c, c.cursor() as cur:
        cur.execute(sql)
        r = cur.fetchone()
        return r[0] if r else None


def _nonnegative_count(value, *, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} returned an invalid row count: {value!r}")
    return value


def _nonnegative_setting(value, *, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _result(chk, status, actual, message):
    check = chk if isinstance(chk, dict) else {}
    return {
        "id": check.get("id", "unknown"),
        "type": check.get("type", "unknown"),
        "table": check.get("table", "*"),
        "desc": check.get("desc", "未提供检查描述"),
        "severity": check.get("severity", "error"),
        "status": status,
        "actual": actual,
        "message": message,
    }


def run_check(chk: dict) -> dict:
    """执行单个健康检查，返回结果（status: ok/warn/fail）。异常 → fail。"""
    try:
        t = chk["type"]
        if t == "volume":
            min_rows = _nonnegative_setting(chk["min_rows"], field="min_rows")
            empties = []
            for name in business_table_names():
                count = _nonnegative_count(_sr_scalar(f"SELECT COUNT(*) FROM `{name}`"), field=name)
                if count < min_rows:
                    empties.append(name)
            if empties:
                return _result(chk, "fail", empties, f"空表：{', '.join(empties)}")
            return _result(chk, "ok", 0, "全部业务表非空")
        if t == "expectation":
            n = _nonnegative_count(_sr_scalar(f"SELECT COUNT(*) FROM `{chk['table']}` WHERE {chk['predicate']}"), field=chk["table"])
            if n > 0:
                return _result(chk, "fail", n, f"{n} 行违反『{chk['predicate']}』")
            return _result(chk, "ok", 0, "无违反行")
        if t == "parity":
            tbl = chk["table"]
            src = _pg_scalar(f"SELECT COUNT(*) FROM {tbl}")
            snk = _sr_scalar(f"SELECT COUNT(*) FROM `{tbl}`")
            actual = {"src": src, "snk": snk}
            if src is None or snk is None:
                return _result(chk, "fail", actual, "源或汇未返回有效行数")
            src = _nonnegative_count(src, field=f"{tbl} source")
            snk = _nonnegative_count(snk, field=f"{tbl} sink")
            actual = {"src": src, "snk": snk}
            if src == snk:
                return _result(chk, "ok", actual, f"源汇一致（{src}）")
            return _result(chk, "fail", actual, f"源↔汇不一致：PG={src} StarRocks={snk} 差 {abs(src - snk)}（疑似 CDC 顿挫/延迟）")
        if t == "schema":
            actual = set(_sr_cols(chk["table"]))
            expect = {c[0] for c in table_by_name(chk["table"])["columns"]}
            missing, extra = expect - actual, actual - expect
            if missing or extra:
                return _result(chk, "warn", {"missing": sorted(missing), "extra": sorted(extra)}, f"结构漂移：缺 {sorted(missing)} 多 {sorted(extra)}")
            return _result(chk, "ok", len(actual), "结构一致")
        if t == "freshness":
            max_age_days = _nonnegative_setting(chk["max_age_days"], field="max_age_days")
            mx = _sr_scalar(f"SELECT MAX(`{chk['column']}`) FROM `{chk['table']}`")
            if mx is None:
                return _result(chk, "warn", None, "无时间数据")
            timestamp = _to_dt(mx)
            now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo is not None else datetime.now()
            age = (now - timestamp).days
            if age < 0:
                return _result(chk, "warn", f"{age}天", "最新时间戳位于未来，检查源系统时钟或时区")
            if age > max_age_days:
                return _result(chk, "warn", f"{age}天", f"数据 {age} 天未更新（阈值 {max_age_days} 天）")
            return _result(chk, "ok", f"{age}天", f"最新数据 {age} 天内")
        if t == "dbt":
            return _dbt_tests_result(chk)
        return _result(chk, "warn", None, f"未知检查类型 {t}")
    except Exception as e:  # noqa: BLE001
        return _result(chk, "fail", None, f"检查执行失败：{str(e)[:100]}")


def _to_dt(v):
    if isinstance(v, datetime):
        return v
    text = str(v).strip()
    if not text:
        raise ValueError("freshness timestamp is empty")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid freshness timestamp: {text[:80]}") from exc


def _dbt_tests_result(chk):
    """读 dbt run_results.json 汇总测试结果（L5 质量门禁并入健康页）。"""
    import json
    import os
    from pathlib import Path
    dbt_dir = Path(os.environ.get("DM_DBT_DIR") or Path(__file__).resolve().parents[3] / "transform" / "dbt")
    rr = dbt_dir / "target" / "run_results.json"
    if not rr.exists():
        return _result(chk, "warn", None, "dbt 尚未运行（无 run_results.json）——先跑 dbt build")
    data = json.loads(rr.read_text(encoding="utf-8"))
    tests = [r for r in data.get("results", []) if r.get("unique_id", "").startswith("test.")]
    bad = [r.get("unique_id", "?").split(".")[2] if len(r.get("unique_id", "").split(".")) > 2 else r.get("unique_id") for r in tests if r.get("status") in ("fail", "error")]
    if bad:
        return _result(chk, "fail", len(bad), f"{len(bad)} 个 dbt 测试未过：{', '.join(bad[:5])}")
    if not tests:
        return _result(chk, "warn", 0, "run_results.json 里没有测试结果（可能只跑了 run）")
    return _result(chk, "ok", len(tests), f"dbt 测试全过（{len(tests)} 个）")


def run_all() -> dict:
    """跑完整监控目录，返回 {results, summary}。"""
    results = [run_check(c) for c in CHECK_CATALOG]
    summary = {"total": len(results), "ok": sum(1 for r in results if r["status"] == "ok"), "warn": sum(1 for r in results if r["status"] == "warn"), "fail": sum(1 for r in results if r["status"] == "fail")}
    return {"results": results, "summary": summary}


def alerts() -> list:
    """当前告警（status != ok），按严重级排序。"""
    res = run_all()["results"]
    order = {"fail": 0, "warn": 1}
    return sorted([r for r in res if r["status"] != "ok"], key=lambda r: (order.get(r["status"], 9), r["severity"]))
