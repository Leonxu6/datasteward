"""🚀 运行驾驶舱：平台/智能体一眼总览。各模块的摘要 + 入口。"""
from __future__ import annotations

import streamlit as st

from .. import charts, components as C, data as D
from . import sync as sync_page
from dm.warehouse.store import read_log


def render():
    flink = D.flink_status()
    pg = D.pg_slots()
    wh = D.wh_health()
    sess = D.agg_sessions(read_log("agent_session"))
    audit = D.agg_audit(read_log("audit_log"))
    ev = D.agg_eval(read_log("eval_run"))
    cdc = flink.get("cdc") or {}
    job_ok = flink.get("ok") and cdc.get("state") == "RUNNING"

    # —— 顶部 KPI 状态卡排（截图门面）——
    C.kpi_row([
        ("数仓连通", wh["latency_ms"] if wh["ok"] else "离线", "ms" if wh["ok"] else "",
         "ok" if wh["ok"] else "bad"),
        ("同步作业", "RUNNING" if job_ok else ("离线" if not flink.get("ok") else cdc.get("state", "—")), "",
         "ok" if job_ok else "bad"),
        ("CDC 延迟", D.fmt_bytes(pg.get("max_lag")) if pg.get("ok") else "—", "",
         "ok" if pg.get("ok") and (pg.get("max_lag") or 0) < 1024 ** 2 else "muted"),
        ("智能体会话", sess["n_sessions"], "", "info"),
        ("MCP 成功率", audit["success_rate"] if audit["success_rate"] is not None else "—",
         "%" if audit["success_rate"] is not None else "", "ok" if (audit["success_rate"] or 0) >= 95 else "warn"),
        ("Eval 通过率", ev["latest"]["rate"] if ev["latest"] else "—",
         "%" if ev["latest"] else "", "ok" if (ev["latest"] or {}).get("rate", 0) >= 85 else "warn"),
    ], min_w=150)

    # —— 实时同步管道缩略 ——
    nodes, foot = sync_page.build_pipeline(flink, pg, wh)
    with C.card("实时同步管道", "PG → Flink CDC → StarRocks"):
        C.pipeline(nodes, foot)

    # —— 智能体活动趋势 + Eval 仪表盘 ——
    a, b = st.columns([3, 2])
    with a:
        with C.card("智能体问答量趋势"):
            if sess["trend_x"]:
                st.plotly_chart(charts.trend_line(sess["trend_x"], sess["trend_y"]),
                                use_container_width=True, config={"displayModeBar": False})
            else:
                st.caption("暂无会话。到『智能体 · 问答入口』提一个问题，这里就会出现趋势。")
    with b:
        with C.card("Eval 通过率"):
            if ev["latest"]:
                st.plotly_chart(charts.gauge(ev["latest"]["rate"]),
                                use_container_width=True, config={"displayModeBar": False})
                st.caption(f'最近跑批 {ev["latest"]["run_id"]} · {ev["latest"]["passed"]}/{ev["latest"]["total"]} 通过')
            else:
                st.caption("暂无评测。运行 dm-eval 后这里显示通过率。")

    # —— 最近问答 + 访问异常 ——
    a, b = st.columns(2)
    with a:
        with C.card("最近问答"):
            if sess["recent"]:
                for r in sess["recent"][:5]:
                    ans = (r["answer"] or "").strip().replace("\n", " ")
                    C.html(
                        f'<div style="padding:9px 0;border-bottom:1px solid {C.T.LINE}">'
                        f'<div style="font-size:13px;color:{C.T.INK}">{C.esc(r["question"][:46])}</div>'
                        f'<div style="font-size:12px;color:{C.T.MUTED};margin-top:3px">'
                        f'{C.chip(r["channel"] or "—", "info")} {C.esc(ans[:60])}</div></div>')
            else:
                st.caption("暂无会话。")
    with b:
        with C.card("访问异常 / 失败调用"):
            if audit["failures"]:
                for f in audit["failures"][:5]:
                    C.html(f'<div style="padding:7px 0;border-bottom:1px solid {C.T.LINE};font-size:12.5px">'
                           f'{C.chip("失败", "bad")} <span style="color:{C.T.INK}">{C.esc(f.get("tool_name", "?"))}</span> '
                           f'<span style="color:{C.T.MUTED}">{C.esc(str(f.get("error", ""))[:60])}</span></div>')
            else:
                C.html(C.status_light("近期无失败调用", "ok"))
