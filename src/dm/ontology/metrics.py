"""指标编译器（L6）：metrics.yaml 的口径定义 → 对 dbt 产出层（DW_SCHEMA）的 SQL。

安全设计：维度/过滤列一律经**白名单**校验（防注入）；过滤值只接受简单字面量。
指标口径改这里（yaml），智能体/报表/eval 三处同步生效——一次定义、处处复用。
"""
import re
from importlib.resources import files

import yaml

from dm.config import DW_SCHEMA as _DW_SCHEMA
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# 过滤表达式白名单形态：col OP value（OP ∈ = != > < >= <=；value 为数字或单引号串）
_FILTER = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(=|!=|>=|<=|>|<)\s*('[^']*'|-?\d+(\.\d+)?)\s*$")

_CACHE = None


def load_metrics() -> dict:
    """读 metrics.yaml → {name: 定义}。进程内缓存。"""
    global _CACHE
    if _CACHE is None:
        raw = yaml.safe_load((files("dm.ontology") / "metrics.yaml").read_text(encoding="utf-8"))
        _CACHE = {m["name"]: m for m in raw.get("metrics", [])}
    return _CACHE


def metric_catalog() -> list:
    """指标字典（对外展示/工具返回）：不含内部实现细节。"""
    return [{
        "name": m["name"], "cn": m.get("cn", ""), "description": m.get("description", ""),
        "unit": m.get("unit", ""), "owner": m.get("owner", ""),
        "dimensions": m.get("dimensions", []),
        "required_markings": m.get("required_markings", []),
        "base_model": m.get("base_model", ""),
    } for m in load_metrics().values()]


def compile_metric(name: str, dimensions: list | None = None, filters: list | None = None,
                   limit: int = 100) -> tuple:
    """编译指标查询。返回 (sql, 定义)。维度/过滤不合法直接抛 ValueError（给调用方转成可读报错）。"""
    m = load_metrics().get(name)
    if not m:
        known = ", ".join(load_metrics().keys())
        raise ValueError(f"未知指标 '{name}'。可用指标：{known}")
    dims = [d.strip() for d in (dimensions or []) if d.strip()]
    allowed = set(m.get("dimensions", []))
    bad = [d for d in dims if d not in allowed]
    if bad:
        raise ValueError(f"维度 {bad} 不在指标 '{name}' 的允许维度内：{sorted(allowed)}")

    conds = list(m.get("default_filters", []))
    for f in (filters or []):
        if not f.strip():
            continue
        mt = _FILTER.match(f)
        if not mt:
            raise ValueError(f"过滤表达式不合法：'{f}'（只接受 列 运算符 字面量，如 material_id='M0001'）")
        col = mt.group(1)
        if col not in allowed and col != m["expr"]:
            raise ValueError(f"过滤列 '{col}' 不在指标 '{name}' 的允许维度内：{sorted(allowed)}")
        conds.append(f.strip())

    agg = m.get("agg", "sum").lower()
    if agg not in ("sum", "count", "count_distinct", "avg", "min", "max"):
        raise ValueError(f"不支持的聚合：{agg}")
    expr = m["expr"]
    if not _IDENT.match(expr):
        raise ValueError(f"表达式列名不合法：{expr}")
    agg_sql = f"COUNT(DISTINCT `{expr}`)" if agg == "count_distinct" else f"{agg.upper()}(`{expr}`)"

    select = [f"`{d}`" for d in dims] + [f"{agg_sql} AS `{name}`"]
    sql = f"SELECT {', '.join(select)} FROM `{_DW_SCHEMA}`.`{m['base_model']}`"
    if conds:
        sql += " WHERE " + " AND ".join(f"({c})" for c in conds)
    if dims:
        sql += " GROUP BY " + ", ".join(f"`{d}`" for d in dims) + f" ORDER BY `{name}` DESC"
    sql += f" LIMIT {max(1, min(int(limit), 500))}"
    return sql, m
