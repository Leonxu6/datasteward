"""指标字典（L6 语义/指标层）：注册口径一览 + 试算。

口径唯一真相源在 dm/ontology/metrics.yaml；智能体（query_metric）、eval、本页三处同源。
试算走与智能体完全相同的编译器与只读连接（不绕过任何治理）。
"""
import pandas as pd
import streamlit as st

from dm.app.errors import safe_error_summary
from dm.ontology.metrics import compile_metric, metric_catalog
from dm.warehouse.store import connect_ro

_MAX_TRIAL_ROWS = 200


def _run_metric_trial(sql: str, *, row_limit: int = _MAX_TRIAL_ROWS) -> tuple[list[str], list]:
    """Run one bounded metric preview and release its cursor and connection."""
    if (
        isinstance(row_limit, bool)
        or not isinstance(row_limit, int)
        or not 1 <= row_limit <= _MAX_TRIAL_ROWS
    ):
        raise ValueError(f"trial row limit must be an integer from 1 to {_MAX_TRIAL_ROWS}")

    with connect_ro() as con:
        with con.execute(sql) as cur:
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = list(cur.fetchmany(row_limit))
    return cols, rows


def render():
    cat = metric_catalog()
    tab_dict, tab_try = st.tabs(["📖 指标字典", "🧮 口径试算"])

    with tab_dict:
        st.caption("一次定义、处处复用：智能体 query_metric / 报表 / eval 同一口径（源：dm/ontology/metrics.yaml）")
        df = pd.DataFrame([{
            "指标名": m["name"], "中文名": m["cn"], "口径说明": m["description"],
            "单位": m["unit"], "负责人": m["owner"],
            "允许维度": ", ".join(m["dimensions"]),
            "所需 Marking": ", ".join(m["required_markings"]) or "—",
            "底表(DW)": m["base_model"],
        } for m in cat])
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_try:
        names = [m["name"] for m in cat]
        col1, col2 = st.columns([1, 2])
        with col1:
            name = st.selectbox("指标", names)
            mdef = next(m for m in cat if m["name"] == name)
            dims = st.multiselect("分组维度", mdef["dimensions"])
            flt = st.text_input("过滤（分号分隔，如 material_id='M0001'）", "")
        with col2:
            st.markdown(f"**{mdef['cn']}** — {mdef['description']}")
            if mdef["required_markings"]:
                st.warning(f"该指标需 Marking：{mdef['required_markings']}（管理台以管理员视角试算；"
                           f"智能体侧按提问者角色/目的强制）")
        if st.button("试算", type="primary"):
            try:
                sql, _ = compile_metric(name, dims, [f for f in flt.split(";") if f.strip()], limit=200)
                st.code(sql, language="sql")
                cols, rows = _run_metric_trial(sql)
                st.dataframe(pd.DataFrame(rows, columns=cols),
                             use_container_width=True, hide_index=True)
            except Exception as e:  # noqa: BLE001
                st.error(safe_error_summary("指标试算", e))
