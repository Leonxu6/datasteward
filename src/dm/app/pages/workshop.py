"""🛠️ Workshop 操作应用（任务队列）——对标 Palantir 的操作型应用(Inbox 模式)。

把数据变成一线可执行的动作：缺料预警 → 一键生成采购申请；可发货订单 → 一键发起发货。
按钮触发**治理化 Action**（默认进待审批，受权限约束、可回滚），而非纯看板——这是 Palantir
"操作型应用 vs 纯仪表盘"的分界：能否经 Action 改变现实。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import components as C
from ..errors import safe_error_summary
from dm.ontology import execute_action
from dm.security import ROLES, User
from dm.warehouse.store import connect_ro


def _q(sql):
    con = connect_ro()
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


def render():
    role = st.selectbox("以角色操作（决定可执行哪些 Action）", ROLES, index=ROLES.index("管理员"))
    u = User("Workshop用户", role, "补货/发货操作")
    C.html('<div class="dm-muted">操作型应用：下面是"待处理任务队列"，点按钮发起治理化 Action（进待审批→审批台批准写回）。</div>')
    t0, t1 = st.tabs(["🔴 缺料预警 → 采购申请", "📦 可发货订单 → 发起发货"])

    with t0:
        try:
            rows = _q(
                "SELECT m.material_id, m.name, m.safety_stock, "
                "COALESCE(SUM(i.qty),0) AS stock "
                "FROM material m LEFT JOIN inventory i ON i.material_id=m.material_id "
                "GROUP BY m.material_id, m.name, m.safety_stock "
                "HAVING COALESCE(SUM(i.qty),0) < m.safety_stock ORDER BY m.material_id")
        except Exception as exc:  # noqa: BLE001
            C.banner(safe_error_summary("读取缺料任务", exc) + "（确认隧道转发 9030）")
            return
        C.kpi_row([("缺料物料数", len(rows), "库存<安全库存", "warn" if rows else "ok")], min_w=160)
        if not rows:
            st.success("无缺料物料。")
        for r in rows[:15]:
            gap = r["safety_stock"] - r["stock"]
            with C.card(f'{r["material_id"]} · {r["name"]}（库存 {r["stock"]} < 安全 {r["safety_stock"]}，缺口 {gap}）'):
                c1, c2, c3 = st.columns([2, 2, 2])
                sup = c1.text_input("供应商", "S001", key=f"sup_{r['material_id']}")
                q = c2.number_input("申请数量", min_value=1, value=int(max(gap, 1)), key=f"q_{r['material_id']}")
                if c3.button("生成采购申请", key=f"pr_{r['material_id']}"):
                    try:
                        res = execute_action(
                            "create_purchase_requisition",
                            {"material_id": r["material_id"], "supplier_id": sup, "qty": int(q)},
                            user=u,
                            approve=False,
                        )
                    except Exception as exc:  # noqa: BLE001
                        C.banner(safe_error_summary("生成采购申请", exc))
                    else:
                        _show(res)

    with t1:
        try:
            rows = _q(
                "SELECT so.so_id, so.material_id, so.qty, COALESCE(inv.stock,0) AS stock "
                "FROM sales_order so LEFT JOIN "
                "(SELECT material_id, SUM(qty) stock FROM inventory GROUP BY material_id) inv "
                "ON inv.material_id=so.material_id WHERE so.status='未完成' ORDER BY so.so_id LIMIT 30")
        except Exception as exc:  # noqa: BLE001
            C.banner(safe_error_summary("读取发货任务", exc))
            return
        shippable = [r for r in rows if r["stock"] >= r["qty"]]
        C.kpi_row([("未完成订单行", len(rows), "", "info"),
                   ("库存充足可发", len(shippable), "", "ok")], min_w=140)
        for r in rows[:15]:
            ok = r["stock"] >= r["qty"]
            tag = "✅ 库存充足" if ok else "⛔ 库存不足"
            with C.card(f'{r["so_id"]} · 物料 {r["material_id"]} 需 {r["qty"]}，库存 {r["stock"]}（{tag}）'):
                c1, c2 = st.columns([3, 2])
                q = c1.number_input("发货数量", min_value=1, value=int(r["qty"]), key=f"dq_{r['so_id']}_{r['material_id']}")
                if c2.button("发起发货", key=f"dn_{r['so_id']}_{r['material_id']}", disabled=not ok):
                    try:
                        res = execute_action(
                            "create_delivery",
                            {"so_id": r["so_id"], "qty": int(q)},
                            user=u,
                            approve=False,
                        )
                    except Exception as exc:  # noqa: BLE001
                        C.banner(safe_error_summary("发起发货", exc))
                    else:
                        _show(res)


def _show(res):
    if res.get("status") == "pending_approval":
        st.warning(f"已进入待审批（去『Action 审批台』批准）：{res.get('message')}")
    elif res.get("ok"):
        st.success(res.get("message"))
    else:
        st.error(res.get("error", "失败"))
