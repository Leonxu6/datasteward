"""✅ 质量 Eval：通过率仪表盘 + 趋势 + 按类别 + 逐条红绿。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import charts, components as C, data as D
from dm.warehouse.store import read_log


def render():
    t0, t1 = st.tabs(["健康总览", "逐条结果"])
    runs = read_log("eval_run")
    e = D.agg_eval(runs)

    with t0:
        if not e["latest"]:
            st.info("暂无评测。运行 dm-eval 后，这里显示通过率、趋势与按类别红绿。")
            return
        lt = e["latest"]
        a, b = st.columns([2, 3])
        with a:
            with C.card("最近通过率", lt["run_id"]):
                st.plotly_chart(charts.gauge(lt["rate"]),
                                use_container_width=True, config={"displayModeBar": False})
        with b:
            C.kpi_row([
                ("最近通过", f'{lt["passed"]}/{lt["total"]}', "", "ok" if lt["rate"] >= 85 else "warn"),
                ("通过率", lt["rate"], "%", "ok" if lt["rate"] >= 85 else "warn"),
                ("跑批数", len(e["trend"]), "", "info"),
            ], min_w=120)
            with C.card("通过率趋势"):
                if len(e["trend"]) >= 1:
                    xs = [t["run_id"][-6:] for t in e["trend"]]
                    ys = [t["rate"] for t in e["trend"]]
                    st.plotly_chart(charts.trend_line(xs, ys, fill=True),
                                    use_container_width=True, config={"displayModeBar": False})
        with C.card("按类别通过率"):
            if e["by_cat"]:
                cats = [c["cat"] for c in e["by_cat"]]
                rates = [c["rate"] for c in e["by_cat"]]
                st.plotly_chart(charts.bar(cats, rates, horizontal=True, fmt=lambda v: f"{v}%"),
                                use_container_width=True, config={"displayModeBar": False})
                C.html(" ".join(C.chip(f'{c["cat"]} {c["passed"]}/{c["total"]}',
                                       "ok" if c["rate"] >= 85 else "warn") for c in e["by_cat"]))

    with t1:
        if not e["order"]:
            st.info("暂无评测。")
            return
        rid = st.selectbox("选择跑批", e["order"][::-1])
        rows = e["by_run"][rid]
        passed = sum(1 for r in rows if r.get("passed"))
        C.kpi_row([
            ("通过", f'{passed}/{len(rows)}', "", "ok" if passed == len(rows) else "warn"),
            ("通过率", round(passed / len(rows) * 100) if rows else 0, "%", "info"),
        ], min_w=120)
        df = pd.DataFrame(rows)
        df.insert(0, "结果", df["passed"].map(lambda p: "✅" if p else "❌"))
        show = [c for c in ["结果", "case_id", "category", "question", "expected", "got", "grader", "session_id"]
                if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True, height=440)
