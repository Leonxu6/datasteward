"""🗄️ 数据仓库：19 张业务表总览 + 表详情（字段定义 + 数据预览）。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import charts, components as C, data as D
from dm.schema import TABLES, table_by_name
from dm.warehouse.store import connect_ro


def render():
    t0, t1 = st.tabs(["表总览", "表详情"])
    stats = D.wh_table_stats()

    with t0:
        if not stats["ok"]:
            C.banner(f'数仓不可达：{stats.get("error", "")[:120]}（确认隧道转发 9030 且已 dm-load）')
            return
        mat = next((r["rows"] for r in stats["rows"] if r["table"] == "material"), None)
        C.kpi_row([
            ("业务表", stats["n_tables"], "", "info"),
            ("总行数", f'{stats["total"]:,}', "", "info"),
            ("已填充表", f'{stats["n_nonempty"]}/{stats["n_tables"]}', "",
             "ok" if stats["n_nonempty"] == stats["n_tables"] else "warn"),
            ("物料数", mat if mat is not None else "—", "", "info"),
            ("数据时间", (stats["freshness"] or "—")[:16], "", "ok" if stats["freshness"] else "muted"),
        ], min_w=132)
        with C.card("各表行数"):
            rows = [r for r in stats["rows"] if r["rows"]]
            rows.sort(key=lambda r: r["rows"], reverse=True)
            if rows:
                st.plotly_chart(
                    charts.bar([r["table"] for r in rows], [r["rows"] for r in rows], horizontal=True),
                    use_container_width=True, config={"displayModeBar": False})
        with C.card("表清单"):
            df = pd.DataFrame([{"表": r["table"], "中文名": r["cn"],
                                "行数": "—" if r["rows"] is None else r["rows"]} for r in stats["rows"]])
            st.dataframe(df, use_container_width=True, hide_index=True, height=360)

    with t1:
        names = [t["name"] for t in TABLES]
        sel = st.selectbox("查看某张表", names,
                           format_func=lambda n: f'{n} · {table_by_name(n)["cn"]}')
        t = table_by_name(sel)
        pk_cols = set(t["pk"].split("+"))
        fk_map = {fk[0]: fk[1] for fk in t["fks"]}
        C.html(f'<div class="dm-h">{C.esc(t["cn"])}</div>'
               f'<div class="dm-muted" style="margin:4px 0 10px">{C.esc(t["desc"])}</div>')
        with C.card("字段定义"):
            cols_df = pd.DataFrame([{
                "列": c[0], "类型": c[1], "中文": c[2],
                "主键": "🔑" if c[0] in pk_cols else "",
                "外键 →": fk_map.get(c[0], ""),
            } for c in t["columns"]])
            st.dataframe(cols_df, use_container_width=True, hide_index=True)
        with C.card("数据预览（前 100 行）"):
            try:
                con = connect_ro()
                try:
                    df = con.execute(f'SELECT * FROM `{sel}` LIMIT 100').fetchdf()
                    st.dataframe(df, use_container_width=True, hide_index=True, height=340)
                finally:
                    con.close()
            except Exception as e:  # noqa: BLE001
                C.banner(f'读取失败：{str(e)[:120]}')
