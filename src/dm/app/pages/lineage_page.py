"""🧬 血缘 Lineage：数据集分层（raw/refined）+ 端到端血缘 + 列级血缘 + 安全随血缘传播。

对标 Palantir 血缘：影响分析（正向）、调试溯源（反向）、合规（provenance）。
数据来自 pipeline/lineage 注册表（无需 DB）。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import components as C
from dm.datasets import datasets, get_dataset
from dm.pipeline.lineage import (
    ancestry, column_lineage, effective_markings, impact, lineage_graph,
)


def render():
    t0, t1 = st.tabs(["数据集分层", "血缘追溯"])
    g = lineage_graph()
    raw, refined = datasets("raw"), datasets("refined")

    with t0:
        C.kpi_row([
            ("raw 数据集", len(raw), "连接器原样落地", "info"),
            ("refined 数据集", len(refined), "清洗整合供本体", "info"),
            ("血缘节点", len(g["nodes"]), "", "info"),
            ("血缘边", len(g["edges"]), "", "info"),
        ], min_w=140)
        C.html('<div class="dm-muted" style="margin:6px 0">链路：连接器 → <b>raw</b>(原样/版本化) '
               '→ transform(清洗/转化/去重/口径统一) → <b>refined</b>(供本体与分析)。'
               '每个 transform 自动登记血缘。</div>')
        with C.card("refined 数据集（清洗整合层）"):
            st.dataframe(pd.DataFrame([{
                "数据集": d.name, "层": d.tier, "产出 transform": d.transform,
                "列数": len(d.columns),
            } for d in refined]), use_container_width=True, hide_index=True, height=380)

    with t1:
        names = [d.name for d in refined]
        ds = st.selectbox("选一个 refined 数据集", names)
        up = ancestry(ds)
        dn = impact(ds)
        C.html(f'<div class="dm-h">{C.esc(ds)}</div>')

        c1, c2 = st.columns(2)
        with c1, C.card("上游 ancestry（它从哪来 · 调试/溯源）"):
            for n in sorted(up, key=lambda x: x["id"]):
                st.markdown(f"- `{n['id']}`  _{n['type']}_")
        with c2, C.card("下游 impact（改它牵连谁 · 影响分析）"):
            if not dn:
                st.caption("无下游")
            for n in sorted(dn, key=lambda x: x["id"]):
                st.markdown(f"- `{n['id']}`")

        with C.card("列级血缘（追溯某列的来源链）"):
            d = get_dataset(ds)
            col = st.selectbox("列", [c[0] for c in d.columns])
            chain = column_lineage(ds, col)
            st.markdown("  →  ".join(
                f"`{s.get('dataset', s.get('source'))}.{s['column']}`" for s in chain))

        em = effective_markings(ds)
        with C.card("有效 Markings（安全随血缘传播）"):
            if em:
                st.markdown("该数据集继承的 Marking：" + " ".join(f"`{m}`" for m in em))
            else:
                st.caption("当前无 Marking（在权限页给源/上游打标后，此处会自动继承——安全随数据跑）")
