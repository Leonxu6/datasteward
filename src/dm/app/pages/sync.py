"""🔄 实时同步监控（HERO）：PG → Flink CDC → StarRocks 活管道。

子标签：管道总览 / Flink 作业 / 复制槽 & 延迟 / 源↔汇对照。
全部走 data.py 的 graceful 探测：隧道未转发 / 组件不可达时降级提示，不崩。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import charts, components as C, data as D
from dm.config import FLINK_URL


def build_pipeline(flink, pg, wh):
    """从三组件实时状态拼出管道节点 + 脚注。dashboard 也复用。"""
    pg_ok = pg.get("ok")
    src = "src" if pg_ok else "down"
    src_desc = f'{pg.get("n_active")} 槽 active' if pg_ok else (
        "驱动缺失" if not pg.get("available") else "不可达")
    cdc = flink.get("cdc")
    running = bool(flink.get("ok") and cdc and cdc.get("state") == "RUNNING")
    flow = "flow" if running else "down"
    flow_desc = (f'{cdc.get("t_running")}/{cdc.get("t_total")} task 运行' if (flink.get("ok") and cdc)
                 else ("不可达" if not flink.get("ok") else "无作业"))
    sink = "sink" if wh.get("ok") else "down"
    sink_desc = f'db={wh.get("db")} · 全量+增量' if wh.get("ok") else "不可达"
    nodes = [
        {"cls": src, "icon": "🐘", "name": "Postgres 源", "desc": src_desc},
        {"cls": flow, "icon": "⚡", "name": "Flink CDC", "desc": flow_desc},
        {"cls": sink, "icon": "⭐", "name": "StarRocks 汇", "desc": sink_desc},
    ]
    foot = []
    if cdc:
        foot.append(f'作业 {cdc.get("state")} · 已运行 {D.fmt_duration(cdc.get("duration_ms"))}')
    if flink.get("version"):
        foot.append(f'Flink {flink["version"]}')
    if flink.get("jobs_failed") is not None:
        foot.append(f'失败作业 {flink["jobs_failed"]}')
    if pg.get("max_lag") is not None:
        foot.append(f'最大复制滞后 {D.fmt_bytes(pg["max_lag"])}')
    return nodes, foot


def render():
    if st.button("🔄 刷新", key="sync_refresh"):
        st.cache_data.clear()
        st.rerun()
    t0, t1, t2, t3 = st.tabs(["管道总览", "Flink 作业", "复制槽 & 延迟", "源↔汇对照"])
    flink = D.flink_status()
    pg = D.pg_slots()
    wh = D.wh_health()

    with t0:
        nodes, foot = build_pipeline(flink, pg, wh)
        with C.card("实时同步管道", "Postgres → Flink CDC → StarRocks · dm-cdc-pg-to-starrocks"):
            C.pipeline(nodes, foot)
        c1, c2, c3 = st.columns(3)
        with c1:
            C.html(C.status_light(f'Postgres 源 · {pg.get("n_active") or 0} 槽',
                                  "ok" if pg.get("ok") else "bad"))
        with c2:
            ok = bool(flink.get("cdc") and flink["cdc"].get("state") == "RUNNING")
            C.html(C.status_light(f'Flink CDC · {flink.get("cdc", {}).get("state", "离线") if flink.get("ok") else "离线"}',
                                  "ok" if ok else "bad"))
        with c3:
            C.html(C.status_light(f'StarRocks 汇 · {"通" if wh.get("ok") else "断"}',
                                  "ok" if wh.get("ok") else "bad"))
        st.write("")
        cdc = flink.get("cdc") or {}
        C.kpi_row([
            ("同步作业", cdc.get("state", "离线") if flink.get("ok") else "离线", "",
             "ok" if cdc.get("state") == "RUNNING" else "bad"),
            ("运行中 task", f'{cdc.get("t_running", "—")}/{cdc.get("t_total", "—")}', "",
             "ok" if cdc.get("t_failed") == 0 else "warn"),
            ("活跃复制槽", pg.get("n_active") if pg.get("ok") else "—", "", "ok" if pg.get("ok") else "muted"),
            ("最大滞后", D.fmt_bytes(pg.get("max_lag")) if pg.get("ok") else "—", "",
             "ok" if (pg.get("max_lag") or 0) < 1024 ** 2 else "warn"),
        ])
        if not flink.get("ok"):
            C.banner(f'Flink REST 不可达（{FLINK_URL}）。请确认 SSH 隧道已转发 8081：'
                     f'ssh -L 8081:127.0.0.1:8081 …  原因：{flink.get("error", "")[:80]}')

    with t1:
        if not flink.get("ok"):
            C.banner(f'Flink REST 不可达（{FLINK_URL}）：{flink.get("error", "")[:120]}')
        else:
            cdc = flink.get("cdc") or {}
            C.kpi_row([
                ("作业状态", cdc.get("state", "—"), "", "ok" if cdc.get("state") == "RUNNING" else "bad"),
                ("已运行", D.fmt_duration(cdc.get("duration_ms")), "", "info"),
                ("task 运行/总", f'{cdc.get("t_running")}/{cdc.get("t_total")}', "", "ok"),
                ("失败 task", cdc.get("t_failed", "—"), "", "ok" if cdc.get("t_failed") == 0 else "bad"),
            ])
            st.write("")
            cc1, cc2, cc3 = st.columns(3)
            cc1.metric("TaskManager", flink.get("taskmanagers", "—"))
            cc2.metric("槽 空闲/总", f'{flink.get("slots_available")}/{flink.get("slots_total")}')
            cc3.metric("运行中作业", flink.get("jobs_running", "—"))
            with C.card("全部作业"):
                jobs = flink.get("jobs", [])
                if jobs:
                    df = pd.DataFrame([{
                        "作业": j["name"], "状态": j["state"],
                        "运行时长": D.fmt_duration(j["duration_ms"]),
                        "task(运行/总)": f'{j["t_running"]}/{j["t_total"]}',
                        "失败": j["t_failed"], "jid": j["jid"][:8],
                    } for j in jobs])
                    st.dataframe(df, use_container_width=True, hide_index=True)
            st.link_button("↗ 打开 Flink Web UI", FLINK_URL, use_container_width=False)
            st.caption("Flink UI 经 SSH 隧道访问（-L 8081:127.0.0.1:8081）。")

    with t2:
        if not pg.get("available"):
            C.banner(pg.get("error", "psycopg 未安装"))
        elif not pg.get("ok"):
            C.banner(f'Postgres 不可达（复制槽读不到）。请确认隧道已转发 15432→5432。原因：{pg.get("error", "")[:90]}')
        else:
            C.kpi_row([
                ("复制槽总数", len(pg["slots"]), "", "info"),
                ("活跃槽", pg["n_active"], "", "ok" if pg["n_active"] == len(pg["slots"]) else "warn"),
                ("最大滞后", D.fmt_bytes(pg["max_lag"]), "", "ok" if (pg["max_lag"] or 0) < 1024 ** 2 else "warn"),
                ("同步机制", "pgoutput · logical", "", "ok"),
            ])
            with C.card("逻辑复制槽 · 滞后明细"):
                df = pd.DataFrame([{
                    "复制槽": s["name"], "活跃": "✅" if s["active"] else "❌",
                    "滞后": D.fmt_bytes(s["lag"]),
                } for s in pg["slots"]])
                st.dataframe(df, use_container_width=True, hide_index=True, height=360)

    with t3:
        par = D.sr_pg_parity()
        if not par.get("ok") and not par.get("pg_ok"):
            C.banner(f'源/汇都读不全：{par.get("error", "")[:120]}')
        C.kpi_row([
            ("对照表数", len(par["rows"]), "", "info"),
            ("行数一致", f'{par["n_match"]}/{len(par["rows"])}', "",
             "ok" if par["n_match"] == len(par["rows"]) else "warn"),
            ("PG 源", "可读" if par.get("pg_ok") else "不可达", "", "ok" if par.get("pg_ok") else "bad"),
        ])
        with C.card("源（Postgres）↔ 汇（StarRocks）行数对照"):
            df = pd.DataFrame([{
                "表": r["table"], "中文名": r["cn"],
                "PG 源": "—" if r["pg"] is None else r["pg"],
                "StarRocks 汇": "—" if r["sr"] is None else r["sr"],
                "一致": "✅" if r["match"] else "⚠️",
            } for r in par["rows"]])
            st.dataframe(df, use_container_width=True, hide_index=True, height=420)
