"""🔐 权限与 Markings：两层安全（强制 Markings AND 自主角色）+ 列级打标 + 判定演示。

对标 Palantir：强制层否决式、自主层加法式、all-or-nothing 合取、属性策略 null 语义、
写回权限独立于读。演示区可选角色+查询，实时看 allow/deny/列屏蔽。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import components as C
from dm.security import (
    ACTION_PERMISSIONS, COLUMN_MARKINGS, MARKINGS, ROLE_MARKINGS, ROLES, User,
    can_execute_action, enforce_query,
)


def render():
    t0, t1 = st.tabs(["角色 · Markings", "判定演示"])

    with t0:
        C.kpi_row([
            ("角色", len(ROLES), "自主层", "info"),
            ("Markings", len(MARKINGS), "强制层", "info"),
            ("列级打标", len(COLUMN_MARKINGS), "属性安全策略", "info"),
            ("治理化 Action", len(ACTION_PERMISSIONS), "写回权限独立", "info"),
        ], min_w=132)
        with C.card("角色 × Markings 资格矩阵（强制层：all-or-nothing 合取）"):
            st.dataframe(pd.DataFrame([{
                "角色": r, **{m: ("✅" if m in ROLE_MARKINGS.get(r, set()) else "—") for m in MARKINGS}
            } for r in ROLES]), use_container_width=True, hide_index=True)
        with C.card("列级打标（属性安全策略 → 列级；缺资格则该列 null）"):
            st.dataframe(pd.DataFrame([{
                "表": t, "列": c, "Markings": ", ".join(ms), "说明": MARKINGS.get(ms[0], "")
            } for (t, c), ms in COLUMN_MARKINGS.items()]),
                use_container_width=True, hide_index=True)
        with C.card("写回 Action 执行权限（独立于读权限）"):
            st.dataframe(pd.DataFrame([{
                "Action": a, "可执行角色": ", ".join(sorted(p["roles"])),
                "需 Markings": ", ".join(sorted(p["markings"])) or "—",
            } for a, p in ACTION_PERMISSIONS.items()]), use_container_width=True, hide_index=True)

    with t1:
        role = st.selectbox("以角色身份", ROLES, index=ROLES.index("仓管"))
        u = User("演示用户", role)
        st.caption(f"该角色 Markings 资格：{sorted(u.markings) or '（无）'}")
        templates = {
            "查客户信用额度（FIN）": ("SELECT customer_id, credit_limit FROM customer", ["customer"]),
            "查员工电话（PII）": ("SELECT name, phone FROM employee", ["employee"]),
            "查采购单价（FIN）": ("SELECT material_id, unit_price FROM purchase_order", ["purchase_order"]),
            "查客户全表（SELECT *，观察列屏蔽）": ("SELECT * FROM customer LIMIT 5", ["customer"]),
            "查库存（无敏感列）": ("SELECT material_id, qty FROM inventory", ["inventory"]),
        }
        tname = st.radio("查询", list(templates), horizontal=False)
        sql, tables = templates[tname]
        st.code(sql, language="sql")
        d = enforce_query(u, sql, tables)
        if d["allow"]:
            C.html('<div class="dm-h" style="color:#128a3a">✅ 放行</div>')
            if d["mask_columns"]:
                st.warning(f"以下列将被屏蔽为 null（属性安全策略）：{d['mask_columns']}")
            else:
                st.caption("无需屏蔽任何列")
        else:
            C.html('<div class="dm-h" style="color:#c0392b">⛔ 拒绝</div>')
            st.error(d["reason"])
            if d["hit_markings"]:
                st.caption(f"命中缺失 Marking：{d['hit_markings']}")

        st.divider()
        st.markdown("**写回权限演示**（独立于读）：调整安全库存阈值 `adjust_safety_stock`")
        ok, reason = can_execute_action(u, "adjust_safety_stock")
        st.success("✅ 该角色可执行") if ok else st.error(f"⛔ {reason}")
