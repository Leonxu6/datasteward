"""数据目录（L9）：全平台"有哪些数据、什么含义、谁负责、什么密级"的图书馆索引。

三源合一：schema.py（19 业务表）+ dbt manifest（DW 分层模型）+ metrics.yaml（指标口径），
Marking 列来自血缘传播后的有效值（effective_markings）。轻量自建；OpenMetadata 为可选重型方案。
"""
import pandas as pd
import streamlit as st

from dm.datasets.model import DATASETS
from dm.ontology.metrics import metric_catalog
from dm.pipeline.lineage import effective_markings
from dm.schema import TABLES, table_by_name


def render():
    tab_tbl, tab_dw, tab_metrics = st.tabs(["🗄️ 业务表（ODS/镜像）", "🏗️ DW 分层（dbt）", "📏 指标口径"])

    with tab_tbl:
        rows = []
        for t in TABLES:
            rows.append({"表": t["name"], "中文名": t["cn"], "说明": t["desc"],
                         "主键": t["pk"], "列数": len(t["columns"]),
                         "Marking(含传播)": ",".join(effective_markings(t["name"])) or "—"})
        for d in DATASETS.values():
            if d.name.startswith("raw_u8__"):
                rows.append({"表": d.name, "中文名": d.description.split("（")[0].replace("U8 ", "U8·"),
                             "说明": d.description, "主键": "-", "列数": len(d.columns) or None,
                             "Marking(含传播)": ",".join(effective_markings(d.name)) or "—"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        sel = st.selectbox("查看列定义", [t["name"] for t in TABLES])
        t = table_by_name(sel)
        if t:
            st.dataframe(pd.DataFrame(
                [{"列": c[0], "类型": c[1], "中文名": c[2]} for c in t["columns"]]),
                use_container_width=True, hide_index=True)

    with tab_dw:
        dw = [d for d in DATASETS.values() if d.tier == "dw"]
        if not dw:
            st.info("dbt manifest 未就绪（先跑 dbt build / dbt parse）——DW 层目录会自动出现在这里。")
        else:
            st.dataframe(pd.DataFrame([{
                "模型": d.name, "落地": d.backing, "说明": d.description,
                "Marking(含传播)": ",".join(effective_markings(d.name)) or "—",
            } for d in dw]), use_container_width=True, hide_index=True)
            st.caption("Marking 沿 dbt 血缘传播：raw_u8__* 的 U8 标自动继承到 DWD/DWS/ADS。")

    with tab_metrics:
        st.dataframe(pd.DataFrame([{
            "指标": m["name"], "中文名": m["cn"], "口径": m["description"], "单位": m["unit"],
            "负责人": m["owner"], "所需 Marking": ",".join(m["required_markings"]) or "—",
            "底表": m["base_model"],
        } for m in metric_catalog()]), use_container_width=True, hide_index=True)
