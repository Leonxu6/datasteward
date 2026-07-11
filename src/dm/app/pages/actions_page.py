"""⚡ Action 审批台：发起治理化写回 → 待审批 → 批准写回 PG → 可回滚 + 历史。

对标 Palantir Action：写回权限(独立)+提交条件+人工审批+事务写回+可回滚+全量审计。
写回目标是 PG 源库（数仓 StarRocks 仍只读），经 Flink CDC 同步回仓。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import components as C
from dm.ontology import (
    ACTION_TYPES, action_history, approve_action, execute_action, list_action_types,
    pending_actions, rollback_action,
)
from dm.security import ROLES, User


def render():
    t0, t1, t2 = st.tabs(["发起 Action", "审批台", "历史"])
    role = st.session_state.setdefault("act_role", "采购")

    with t0:
        role = st.selectbox("以角色身份操作", ROLES, index=ROLES.index(role), key="act_role")
        u = User("审批台用户", role, "写回操作")
        acts = list_action_types()
        a = st.selectbox("Action", [x["action"] for x in acts],
                         format_func=lambda k: next(x["display_name"] for x in acts if x["action"] == k))
        meta = ACTION_TYPES[a]
        C.html(f'<div class="dm-muted">{C.esc(meta["rule"])}｜提交条件：{C.esc(meta["submission_criteria"])}</div>')
        defaults = {"material_id": "M0001", "new_value": 20, "supplier_id": "S001",
                    "qty": 10, "so_id": "SO0001"}
        params = {}
        for p in meta["parameters"]:
            key = f"ap_{a}_{p['name']}"
            if p["type"] == "Integer":
                params[p["name"]] = st.number_input(f'{p["name"]} · {p["desc"]}', min_value=0,
                                                    value=int(defaults.get(p["name"], 0)), step=1, key=key)
            else:
                params[p["name"]] = st.text_input(f'{p["name"]} · {p["desc"]}',
                                                  str(defaults.get(p["name"], "")), key=key)
        if st.button("发起（默认进入待审批，不直接写库）", type="primary"):
            try:
                res = execute_action(a, params, user=u, approve=False)
                if res.get("status") == "pending_approval":
                    st.warning(f"已进入待审批：{res.get('message')}（action_id={res['action_id']}）")
                    st.json(res.get("preview", {}))
                elif res.get("ok"):
                    st.success(res.get("message"))
                else:
                    st.error(res.get("error", "失败"))
            except Exception as e:  # noqa: BLE001
                C.banner(f'发起失败（可能 PG 源不可达，确认隧道转发 15432）：{str(e)[:140]}')

    with t1:
        approver = st.selectbox("审批人角色", ROLES, index=ROLES.index("管理层"), key="approver_role")
        au = User("审批人", approver)
        pend = []
        try:
            pend = pending_actions()
        except Exception as e:  # noqa: BLE001
            C.banner(f'读取待审批失败：{str(e)[:120]}')
        if not pend:
            st.caption("暂无待审批 Action")
        for r in pend:
            with C.card(f"{r['action']} · {r['target']}  ({r['before']} → {r['after']})"):
                st.caption(f"发起人 {r['user']}（{r['role']}）· {r['ts']} · id={r['action_id']}")
                c1, c2 = st.columns(2)
                if c1.button("✅ 批准并写回", key="ap_" + r["action_id"]):
                    try:
                        res = approve_action(r["action_id"], user=au)
                        st.success(res.get("message") or res.get("error"))
                    except Exception as e:  # noqa: BLE001
                        C.banner(f'批准失败：{str(e)[:140]}')
                if c2.button("↩ 忽略", key="ig_" + r["action_id"]):
                    st.info("已忽略（保留待审批记录）")

    with t2:
        hist = []
        try:
            hist = action_history()
        except Exception as e:  # noqa: BLE001
            C.banner(f'读取历史失败：{str(e)[:120]}')
        if not hist:
            st.caption("暂无 Action 历史")
            return
        st.dataframe(pd.DataFrame([{
            "时间": r["ts"], "Action": r["action"], "对象": r["target"],
            "变更": f'{r["before"]} → {r["after"]}', "状态": r["status"],
            "发起人": f'{r["user"]}({r["role"]})',
        } for r in hist]), use_container_width=True, hide_index=True, height=360)
        # 回滚入口
        executed = [r for r in hist if r["status"] == "executed" and not r.get("rolled_back")]
        if executed:
            rb_role = st.selectbox("回滚操作角色", ROLES, index=ROLES.index("管理层"), key="rb_role")
            rid = st.selectbox("选择已执行 Action 回滚", [r["action_id"] for r in executed])
            if st.button("↩ 回滚（还原 PG）"):
                try:
                    res = rollback_action(rid, user=User("回滚人", rb_role))
                    st.success(res.get("message") or res.get("error"))
                except Exception as e:  # noqa: BLE001
                    C.banner(f'回滚失败：{str(e)[:140]}')
