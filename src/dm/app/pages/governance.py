"""🛡️ 访问治理：MCP 每次工具调用留痕 = 数据访问全程可审计。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import charts, components as C, data as D
from .. import theme as T
from dm.warehouse.store import read_log

_ORDER = ["ts", "session_id", "channel", "tool_name", "tool_args", "sql",
          "tables_touched", "row_count", "duration_ms", "ok", "error"]


def render():
    t0, t1 = st.tabs(["调用总览", "审计明细"])
    logs = read_log("audit_log")
    a = D.agg_audit(logs)

    with t0:
        if not logs:
            st.info("暂无审计记录。智能体经 MCP 连接器访问数据后，每次调用都会在此留痕。")
            return
        C.kpi_row([
            ("调用次数", a["total"], "", "info"),
            ("成功率", a["success_rate"], "%", "ok" if (a["success_rate"] or 0) >= 95 else "warn"),
            ("平均耗时", a["avg_ms"] if a["avg_ms"] is not None else "—", "ms", "info"),
            ("失败数", a["fail"], "", "ok" if a["fail"] == 0 else "bad"),
        ])
        x, y = st.columns([2, 3])
        with x:
            with C.card("工具占比"):
                if a["by_tool"]:
                    st.plotly_chart(charts.donut(list(a["by_tool"].keys()), list(a["by_tool"].values()),
                                                 center=a["total"]),
                                    use_container_width=True, config={"displayModeBar": False})
                    C.html(" ".join(C.chip(f'{k} {v}', "info") for k, v in a["by_tool"].items()))
        with y:
            with C.card("调用耗时分布"):
                if a["durations"]:
                    st.plotly_chart(charts.latency_hist(a["durations"]),
                                    use_container_width=True, config={"displayModeBar": False})
                else:
                    st.caption("暂无耗时数据。")
        x, y = st.columns(2)
        with x:
            with C.card("命中表 Top"):
                if a["by_table"]:
                    C.bar_list([(t, n) for t, n in a["by_table"]])
                else:
                    st.caption("暂无。")
        with y:
            with C.card("失败调用"):
                if a["failures"]:
                    for f in a["failures"][:6]:
                        C.html(f'<div style="padding:7px 0;border-bottom:1px solid {T.LINE};font-size:12.5px">'
                               f'{C.chip("失败", "bad")} <b style="font-weight:500">{C.esc(f.get("tool_name", "?"))}</b> '
                               f'<span style="color:{T.MUTED}">{C.esc(str(f.get("error", ""))[:70])}</span></div>')
                else:
                    C.html(C.status_light("近期无失败调用", "ok"))

    with t1:
        if not logs:
            st.info("暂无审计记录。")
            return
        df = pd.DataFrame(logs)
        f1, f2 = st.columns(2)
        chans = sorted(x for x in df.get("channel", pd.Series()).dropna().unique())
        tools = sorted(x for x in df.get("tool_name", pd.Series()).dropna().unique())
        pick_c = f1.multiselect("通道", chans, default=chans)
        pick_t = f2.multiselect("工具", tools, default=tools)
        if pick_c:
            df = df[df["channel"].isin(pick_c)]
        if pick_t:
            df = df[df["tool_name"].isin(pick_t)]
        cols = [c for c in _ORDER if c in df.columns] + [c for c in df.columns if c not in _ORDER]
        st.dataframe(df[cols].iloc[::-1], use_container_width=True, hide_index=True, height=460)
