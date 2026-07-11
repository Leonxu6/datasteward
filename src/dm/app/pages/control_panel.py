"""🛰️ 管理者 Control Panel：平台运维的单一视图（对标 Palantir Control Panel）。

管理者/运维一眼看清：平台清单（对象/数据集/源）、访问治理（角色/Markings/Action 权限）、
资源目录（数据集 + 有效 Markings）、活动与审计总览（谁在用、allow/deny、按分类/角色）。
面向"管理者能看到什么"——聚合视图，不重复各功能页的细节。
"""
from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from .. import charts, components as C
from dm.connect import list_sources
from dm.datasets import datasets
from dm.ontology import list_action_types, object_types
from dm.pipeline.lineage import effective_markings, lineage_graph
from dm.security import ACTION_PERMISSIONS, COLUMN_MARKINGS, MARKINGS, ROLE_MARKINGS, ROLES
from dm.warehouse.store import read_log


def render():
    t0, t1, t2, t3 = st.tabs(["平台总览", "用户与权限", "资源目录", "活动与审计"])
    ots = object_types()
    raw, refined = datasets("raw"), datasets("refined")
    srcs = list_sources()
    g = lineage_graph()

    with t0:
        C.kpi_row([
            ("对象类型", len(ots), "Ontology", "info"),
            ("数据集", f"{len(raw)}+{len(refined)}", "raw+refined", "info"),
            ("连接源", len(srcs), "Data Connection", "info"),
            ("角色", len(ROLES), "自主层", "info"),
            ("Markings", len(MARKINGS), "强制层", "info"),
            ("Action 类型", len(list_action_types()), "写回", "info"),
            ("血缘节点/边", f"{len(g['nodes'])}/{len(g['edges'])}", "", "info"),
        ], min_w=118)
        C.html('<div class="dm-muted" style="margin-top:8px">Palantir-格式分层：'
               '连接器 → raw/refined 数据集 → Ontology 对象 → 治理(权限/审计/血缘) → Action 写回 → 消费(AIP/Workshop)。</div>')

    with t1:
        with C.card("角色 × Markings 资格矩阵（强制层 all-or-nothing 合取）"):
            st.dataframe(pd.DataFrame([{
                "角色": r, **{m: ("✅" if m in ROLE_MARKINGS.get(r, set()) else "—") for m in MARKINGS}
            } for r in ROLES]), use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1, C.card("写回 Action 执行权限（独立于读）"):
            st.dataframe(pd.DataFrame([{
                "Action": a, "可执行角色": ", ".join(sorted(p["roles"]))
            } for a, p in ACTION_PERMISSIONS.items()]), use_container_width=True, hide_index=True)
        with c2, C.card("列级打标（属性安全策略）"):
            st.dataframe(pd.DataFrame([{
                "表.列": f"{t}.{c}", "Markings": ", ".join(ms)
            } for (t, c), ms in COLUMN_MARKINGS.items()]), use_container_width=True, hide_index=True)

    with t2:
        with C.card("数据集目录（含沿血缘传播的有效 Markings）"):
            rows = []
            for d in refined:
                em = effective_markings(d.name)
                rows.append({"数据集": d.name, "层": d.tier, "列数": len(d.columns),
                             "有效 Markings": ", ".join(em) or "—"})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=300)
        with C.card("连接源目录"):
            st.dataframe(pd.DataFrame([{
                "源": s.name, "类型": s.source_type,
                "凭据引用": ", ".join(s.credential_env.keys()) or "—",
                "源打标": ", ".join(s.markings) or "—", "说明": s.description,
            } for s in srcs]), use_container_width=True, hide_index=True)

    with t3:
        audit = read_log("audit_log")
        if not audit:
            C.banner("暂无审计记录（智能体/钉钉/eval 运行后此处会有数据）。")
            return
        n = len(audit)
        deny = sum(1 for r in audit if r.get("decision") == "deny")
        allow = sum(1 for r in audit if r.get("decision") == "allow")
        C.kpi_row([
            ("审计条数", n, "", "info"),
            ("放行", allow, "", "ok"),
            ("拒绝", deny, "authorizationCheck", "warn" if deny else "ok"),
            ("涉及角色", len({r.get("role", "") for r in audit if r.get("role")}), "", "info"),
        ], min_w=120)
        cat = Counter(r.get("category", "?") for r in audit)
        role = Counter(r.get("role", "?") for r in audit if r.get("role"))
        c1, c2 = st.columns(2)
        with c1, C.card("按审计分类"):
            if cat:
                st.plotly_chart(charts.bar(list(cat.keys()), list(cat.values()), horizontal=True),
                                use_container_width=True, config={"displayModeBar": False})
        with c2, C.card("按操作角色"):
            if role:
                st.plotly_chart(charts.bar(list(role.keys()), list(role.values()), horizontal=True),
                                use_container_width=True, config={"displayModeBar": False})
        with C.card("最近活动（后 20 条）"):
            st.dataframe(pd.DataFrame([{
                "时间": r.get("ts", ""), "分类": r.get("category", ""), "决策": r.get("decision", ""),
                "角色": r.get("role", ""), "工具": r.get("tool_name", ""),
                "命中 Marking": r.get("markings", ""),
            } for r in audit[-20:][::-1]]), use_container_width=True, hide_index=True, height=300)
