"""🧩 本体 Ontology：对象类型总览 + Object Explorer（对象→属性→链接→可用 Action）。

对标 Palantir Workshop 的对象视图：从对象类型进入某个实例，看它的属性、上下游链接
（Search-Around）与可执行的治理化 Action。数据经 OSDK-lite（受权限约束）。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import components as C
from dm.ontology import (
    ONTOLOGY, get_links, get_object, get_object_type, list_action_types,
    list_objects, object_types, to_camel,
)
from dm.security import ROLES, User


def render():
    t0, t1 = st.tabs(["本体总览", "Object Explorer"])
    ots = object_types()
    acts = list_action_types()

    with t0:
        n_links = sum(len(o.links) for o in ots)
        C.kpi_row([
            ("对象类型", len(ots), "", "info"),
            ("链接类型", n_links, "", "info"),
            ("Action 类型", len(acts), "", "info"),
            ("语义分组", len({o.group for o in ots}), "", "info"),
        ], min_w=132)
        with C.card("对象类型清单（派生自 schema.py，1 数据源 ↔ 1 对象类型）"):
            df = pd.DataFrame([{
                "对象(API)": o.api_name, "中文": o.display_name, "背书数据源": o.table,
                "主键": "+".join(o.primary_key), "分组": o.group,
                "#属性": len(o.properties), "#出向链接": len(o.links),
            } for o in ots])
            st.dataframe(df, use_container_width=True, hide_index=True, height=420)
        with C.card("Action 类型（本体写回动词层）"):
            st.dataframe(pd.DataFrame([{
                "Action": a["action"], "名称": a["display_name"], "作用对象": a["object_type"],
                "参数": ", ".join(p["name"] for p in a["parameters"]),
                "提交条件": a["submission_criteria"],
            } for a in acts]), use_container_width=True, hide_index=True)

    with t1:
        cc = st.columns([2, 2, 2])
        role = cc[0].selectbox("以角色浏览", ROLES, index=ROLES.index("仓管"), key="oe_role")
        purpose = cc[1].text_input("访问目的 (PBAC)", "发货核对", key="oe_purpose")
        wh = cc[2].text_input("管辖仓库 (仓管行级)", "W02", key="oe_wh")
        u = User("浏览用户", role, purpose, attrs={"warehouse_id": wh} if wh else {})
        C.html('<div class="dm-muted">对象层按权限强制：表级可见性 + 行级对象策略 + 列级属性屏蔽（=单元格级）。'
               '切角色/目的/仓库观察差异。</div>')
        names = [o.api_name for o in ots]
        api = st.selectbox("对象类型", names,
                           format_func=lambda a: f'{a} · {get_object_type(a).display_name}')
        ot = get_object_type(api)
        pk_api = to_camel(ot.primary_key[0])
        try:
            listing = list_objects(api, limit=50, user=u)
        except Exception as e:  # noqa: BLE001
            C.banner(f'数仓不可达：{str(e)[:120]}（确认 SSH 隧道转发 9030 且已 dm-load）')
            return
        if listing.get("error"):
            C.banner("⛔ " + listing["error"])
            return
        if listing.get("row_policy"):
            st.caption(f"🔒 已按行级策略过滤：仅显示仓库 {wh} 的行")
        objs = listing.get("objects", [])
        if not objs:
            C.banner("该对象类型暂无实例数据。")
            return
        pk_val = st.selectbox(
            f"选择实例（{ot.display_name}，共 {listing['count']} 显示）",
            [o.get(pk_api) for o in objs],
            format_func=lambda v: f'{v} · {next((o.get(ot_title(ot)) for o in objs if o.get(pk_api) == v), "")}')

        obj = get_object(api, pk_val, user=u).get("object", {})
        C.html(f'<div class="dm-h">{C.esc(ot.display_name)} · {C.esc(str(pk_val))}</div>')
        with C.card("属性"):
            st.dataframe(pd.DataFrame(
                [{"属性": p.api_name, "中文": p.display_name, "类型": p.base_type,
                  "值": obj.get(p.api_name)} for p in ot.properties],
            ), use_container_width=True, hide_index=True)

        links = get_links(api, pk_val)
        c1, c2 = st.columns(2)
        with c1, C.card("出向链接（→ 父对象）"):
            og = links.get("outgoing", {})
            if not og:
                st.caption("无")
            for rel, info in og.items():
                st.markdown(f"**{rel}** → {info['to']}：{info['object'].get(ot_title(get_object_type(info['to'])), '')}")
        with c2, C.card("入向链接（子对象 ← 本对象，Search-Around）"):
            ic = links.get("incoming", {})
            if not ic:
                st.caption("无")
            for rel, info in ic.items():
                st.markdown(f"**{rel}** ← {info['from']}（{info['count']} 条）")

        with C.card("可用 Action（治理化写回）"):
            rel_acts = [a for a in list_action_types() if a["object_type"] == api]
            if not rel_acts:
                st.caption("该对象类型暂无可用 Action")
            for a in rel_acts:
                st.markdown(f"- **{a['display_name']}**（`{a['action']}`）→ 见「Action 审批台」执行；"
                            f"受写回权限约束、需审批、可回滚")


def ot_title(ot):
    """对象类型的展示属性 api_name。"""
    return to_camel(ot.title_property)
