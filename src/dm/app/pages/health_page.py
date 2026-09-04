"""🩺 数据健康：监控目录 + 阈值告警（对标 Palantir Data Health）。

跑完整监控目录（新鲜度/量/期望/源汇对账/结构），红黄绿呈现 + 告警清单。
源↔汇对账是 CDC 顿挫探测器：PG 与 StarRocks 行数不一致即告警。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import components as C
from ..errors import safe_error_summary
from dm.health import CHECK_CATALOG, run_all


_ICON = {"ok": "🟢", "warn": "🟡", "fail": "🔴"}


def render():
    t0, t1 = st.tabs(["监控总览", "监控目录"])
    try:
        data = run_all()
    except Exception as exc:  # noqa: BLE001
        C.banner(safe_error_summary("健康检查", exc) + "（确认隧道转发 9030/15432）")
        return
    res, s = data["results"], data["summary"]

    with t0:
        C.kpi_row([
            ("检查项", s["total"], "监控目录", "info"),
            ("🟢 正常", s["ok"], "", "ok"),
            ("🟡 警告", s["warn"], "", "warn" if s["warn"] else "ok"),
            ("🔴 失败", s["fail"], "", "warn" if s["fail"] else "ok"),
        ], min_w=120)

        alerts = [r for r in res if r["status"] != "ok"]
        if alerts:
            with C.card("🚨 当前告警"):
                for r in sorted(alerts, key=lambda x: 0 if x["status"] == "fail" else 1):
                    st.markdown(f'{_ICON[r["status"]]} **{r["desc"]}**（{r["table"]}·{r["severity"]}）：{r["message"]}')
        else:
            st.success("✅ 全部健康检查通过，无告警。")

        with C.card("全部检查结果"):
            st.dataframe(pd.DataFrame([{
                "状态": _ICON[r["status"]], "检查": r["desc"], "表": r["table"],
                "类型": r["type"], "严重级": r["severity"], "详情": r["message"],
            } for r in res]), use_container_width=True, hide_index=True, height=380)

    with t1:
        C.html('<div class="dm-muted">监控目录（可配置阈值/严重级；对标 Palantir Health Check 配置）。</div>')
        st.dataframe(pd.DataFrame([{
            "id": c["id"], "类型": c["type"], "对象": c.get("table", "所有业务表"),
            "严重级": c["severity"],
            "阈值/参数": c.get("predicate") or c.get("min_rows") or c.get("max_age_days") or "-",
            "说明": c["desc"],
        } for c in CHECK_CATALOG]), use_container_width=True, hide_index=True, height=380)
