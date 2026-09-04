"""📊 报表：管理者仪表盘 + 字段级业务报表（对标 Palantir Workshop 报表 / Object Table）。

管理者一眼看到关键经营 KPI + 若干可下钻的业务报表（库存概览/缺料清单/采购在途/销售履约），
每个报表列头取自 Ontology 的中文属性名。数字与后台真实数据一致（可对账）。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import charts, components as C
from ..errors import safe_error_summary
from dm.warehouse.store import connect_ro


def _df(sql):
    con = connect_ro()
    try:
        return con.execute(sql).fetchdf()
    finally:
        con.close()


def _scalar(sql):
    con = connect_ro()
    try:
        return con.execute(sql).fetchone()[0]
    finally:
        con.close()


def render():
    t0, t1 = st.tabs(["管理者仪表盘", "业务报表"])
    try:
        with t0:
            _dashboard()
        with t1:
            _reports()
    except Exception as exc:  # noqa: BLE001
        C.banner(safe_error_summary("加载经营报表", exc) + "（确认隧道转发 9030 且已 dm-load）")


def _dashboard():
    n_mat = _scalar("SELECT COUNT(*) FROM material")
    inv_qty = _scalar("SELECT COALESCE(SUM(qty),0) FROM inventory")
    open_po = _scalar("SELECT COUNT(DISTINCT po_id) FROM purchase_order WHERE status='未完成'")
    open_so = _scalar("SELECT COUNT(DISTINCT so_id) FROM sales_order WHERE status='未完成'")
    low = _scalar("SELECT COUNT(*) FROM (SELECT m.material_id FROM material m "
                  "LEFT JOIN inventory i ON i.material_id=m.material_id "
                  "GROUP BY m.material_id, m.safety_stock "
                  "HAVING COALESCE(SUM(i.qty),0) < m.safety_stock) t")
    deliv = _scalar("SELECT COUNT(*) FROM delivery_note")
    C.kpi_row([
        ("物料数", n_mat, "主数据", "info"),
        ("库存总量", f"{inv_qty:,}", "即时库存", "info"),
        ("未完成采购单", open_po, "在途", "info"),
        ("未完成销售订单", open_so, "待履约", "info"),
        ("缺料物料", low, "低于安全库存", "warn" if low else "ok"),
        ("发货单", deliv, "累计", "info"),
    ], min_w=120)
    with C.card("各仓库库存量"):
        df = _df("SELECT warehouse_id, SUM(qty) AS qty FROM inventory GROUP BY warehouse_id ORDER BY warehouse_id")
        if not df.empty:
            st.plotly_chart(charts.bar(df["warehouse_id"].tolist(), df["qty"].tolist(), horizontal=True),
                            use_container_width=True, config={"displayModeBar": False})


_REPORTS = {
    "库存概览（物料×仓库）": (
        "SELECT i.material_id AS 物料, m.name AS 物料名称, i.warehouse_id AS 仓库, "
        "SUM(i.qty) AS 数量 FROM inventory i LEFT JOIN material m ON m.material_id=i.material_id "
        "GROUP BY i.material_id, m.name, i.warehouse_id ORDER BY i.material_id LIMIT 200"),
    "缺料清单（低于安全库存）": (
        "SELECT m.material_id AS 物料, m.name AS 物料名称, m.safety_stock AS 安全库存, "
        "COALESCE(SUM(i.qty),0) AS 现有库存, m.safety_stock-COALESCE(SUM(i.qty),0) AS 缺口 "
        "FROM material m LEFT JOIN inventory i ON i.material_id=m.material_id "
        "GROUP BY m.material_id, m.name, m.safety_stock "
        "HAVING COALESCE(SUM(i.qty),0) < m.safety_stock ORDER BY 缺口 DESC LIMIT 200"),
    "采购在途（未完成采购单）": (
        "SELECT po_id AS 采购单, supplier_id AS 供应商, material_id AS 物料, qty AS 数量, "
        "expected_date AS 预计到货, status AS 状态 FROM purchase_order "
        "WHERE status='未完成' ORDER BY expected_date LIMIT 200"),
    "销售履约（订单 vs 已发）": (
        "SELECT so.so_id AS 销售单, so.material_id AS 物料, so.qty AS 订单量, "
        "COALESCE(d.shipped,0) AS 已发, so.qty-COALESCE(d.shipped,0) AS 待发 FROM sales_order so "
        "LEFT JOIN (SELECT so_id, material_id, SUM(qty) shipped FROM delivery_note "
        "GROUP BY so_id, material_id) d ON d.so_id=so.so_id AND d.material_id=so.material_id "
        "ORDER BY so.so_id LIMIT 200"),
}


def _reports():
    name = st.selectbox("选择报表", list(_REPORTS))
    df = _df(_REPORTS[name])
    C.kpi_row([("记录数", len(df), "", "info")], min_w=120)
    st.dataframe(df, use_container_width=True, hide_index=True, height=460)
    st.caption("字段级报表（列头取自业务语义）。导出上限对标 Palantir Object Table（前端 200 行/导出另限），"
               "此处演示前 200 行。")
