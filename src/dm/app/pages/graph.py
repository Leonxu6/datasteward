"""🕸️ 知识图谱：实体关系层（结构化 FK 骨架 + 文档抽取的新关系，存于 Neo4j）。

观测图规模（节点/边/按标签/按关系）+ 跨域多跳查询（find_related / impact_path），与智能体 graph_query 同源。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import components as C
from ..errors import safe_error_summary


def render():
    try:
        from dm.kg.query import find_related, impact_path
        from dm.kg.store import counts, ping
    except Exception as exc:  # noqa: BLE001
        C.banner(safe_error_summary("KG 模块加载", exc) + "（需 pip install -e .[kg]）")
        return
    try:
        ok, err = ping()
    except Exception as exc:  # noqa: BLE001
        C.banner(safe_error_summary("Neo4j 健康检查", exc) + "（确认隧道转发 7687 且已 dm-kg build）")
        return
    if not ok:
        C.banner("Neo4j 不可达（确认隧道转发 7687 且已 dm-kg build）")
        return
    try:
        c = counts()
    except Exception as exc:  # noqa: BLE001
        C.banner(safe_error_summary("读取图谱统计", exc))
        return
    C.kpi_row([
        ("节点", f'{c["nodes"]:,}', "", "info"),
        ("边", f'{c["edges"]:,}', "", "info"),
        ("文档抽取关系", c["doc_extracted"], "", "ok" if c["doc_extracted"] else "muted"),
        ("实体类型", len(c["by_label"]), "", "info"),
    ], min_w=140)

    t_q, t_stat = st.tabs(["跨域查询", "图谱规模"])

    with t_stat:
        with C.card("节点（按标签）", "结构化业务行 → 节点"):
            C.bar_list([(k, v) for k, v in list(c["by_label"].items())[:14]])
        with C.card("关系（按类型）", "FK 骨架 + 文档抽取（source=doc）"):
            C.bar_list([(k, v) for k, v in list(c["by_rel"].items())[:14]])

    with t_q:
        st.caption("与智能体 graph_query 同源。impact_path=从某实体到某类实体的最短影响路径（断供/溯源）；find_related=N 跳邻居。")
        col1, col2, col3 = st.columns([2, 2, 1])
        eid = col1.text_input("实体 ID", value="S001", placeholder="如 S001 / M0001 / CNC-08")
        mode = col2.selectbox("模式", ["impact_path → Customer", "impact_path → SalesOrder", "find_related"])
        hops = col3.number_input("最大跳数", 1, 6, 4)
        if st.button("查询", type="primary") and eid.strip():
            try:
                if mode.startswith("find_related"):
                    r = find_related(eid.strip(), max_hops=int(hops), limit=40)
                    C.kpi_row([("相连实体", r["count"], "", "ok" if r["count"] else "muted")], min_w=140)
                    if r["related"]:
                        df = pd.DataFrame(r["related"])
                        st.dataframe(df[["type", "id", "name", "cn", "hops", "via"]],
                                     use_container_width=True, hide_index=True, height=400)
                else:
                    tt = "Customer" if "Customer" in mode else "SalesOrder"
                    r = impact_path(eid.strip(), tt, max_hops=int(hops), limit=20)
                    if r.get("error"):
                        C.banner(r["error"])
                        return
                    C.kpi_row([(f"受影响 {tt}", r["count"], "", "ok" if r["count"] else "muted")], min_w=160)
                    for x in r.get("paths", []):
                        with C.card(f'{x["name"]}（{x["id"]}）· {x["hops"]} 跳'):
                            C.html('<div style="font-size:13px;line-height:1.9">'
                                   + '　<span style="color:#999">→</span>　'.join(C.esc(p) for p in x["path"])
                                   + '</div>')
                            C.html(" ".join(C.chip(rl, "info") for rl in x["rels"]))
            except Exception as exc:  # noqa: BLE001
                C.banner(safe_error_summary("图谱查询", exc))
