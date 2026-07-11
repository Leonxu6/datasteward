"""🧠 智能体：活动总览 / 任务链回放（垂直时间线）/ 问答入口。"""
from __future__ import annotations

import streamlit as st

from .. import charts, components as C, data as D
from dm.warehouse.store import read_log

_EXAMPLES = [
    "物料 M0001 现在总库存多少？分布在哪些仓库？",
    "销售订单 SO0001 现在的库存够不够发货？",
    "供应商 S001 有哪些未完成的采购单？",
    "M0001 明天的人员排班和产能够吗？",
]
_KLABEL = {"question": "提问", "plan": "计划", "tool_call": "调工具", "tool_result": "结果", "answer": "答案"}
_KIND = {"question": "question", "plan": "plan", "tool_call": "tool", "tool_result": "result", "answer": "answer"}


def _tool_body(content):
    name, args = D.parse_tool_call(content)
    if name == "run_sql":
        return f'调工具 · run_sql', C.sql_card(args.get("sql", ""))
    if name == "describe_table":
        return "调工具 · describe_table", C.bubble(f'describe_table（{args.get("name", "")}）')
    if name == "list_tables":
        return "调工具 · list_tables", C.bubble("list_tables")
    return f"调工具 · {name}", C.bubble(str(args)[:300])


def _timeline_items(steps):
    items = []
    for s in steps:
        stype = s.get("step_type")
        content = s.get("content", "")
        if stype == "question":
            continue  # 作为头部展示
        if stype == "tool_call":
            label, body = _tool_body(content)
        elif stype == "tool_result":
            label, body = "结果", C.bubble(str(content)[:600])
        elif stype == "answer":
            label, body = "答案", C.answer_card(s.get("final_answer") or content)
        else:  # plan
            label, body = "计划", C.bubble(str(content))
        items.append({"kind": _KIND.get(stype, "plan"), "label": label, "body_html": body})
    return items


def render():
    t0, t1, t2 = st.tabs(["活动总览", "任务链回放", "问答入口"])
    steps = read_log("agent_session")
    s = D.agg_sessions(steps)

    with t0:
        C.kpi_row([
            ("会话数", s["n_sessions"], "", "info"),
            ("问答数", s["n_questions"], "", "info"),
            ("平均步数", s["avg_steps"] if s["avg_steps"] is not None else "—", "步", "info"),
            ("通道数", len(s["by_channel"]), "", "info"),
        ])
        a, b = st.columns([2, 3])
        with a:
            with C.card("通道分布"):
                if s["by_channel"]:
                    labels = list(s["by_channel"].keys())
                    st.plotly_chart(charts.donut(labels, list(s["by_channel"].values()),
                                                 center=s["n_sessions"]),
                                    use_container_width=True, config={"displayModeBar": False})
                    C.html(" ".join(C.chip(f'{k} {v}', "info") for k, v in s["by_channel"].items()))
                else:
                    st.caption("暂无会话。")
        with b:
            with C.card("问答量趋势"):
                if s["trend_x"]:
                    st.plotly_chart(charts.trend_line(s["trend_x"], s["trend_y"]),
                                    use_container_width=True, config={"displayModeBar": False})
                else:
                    st.caption("暂无会话。")
        with C.card("最近问答"):
            if s["recent"]:
                for r in s["recent"][:8]:
                    ans = (r["answer"] or "").strip().replace("\n", " ")
                    C.html(
                        f'<div style="padding:9px 0;border-bottom:1px solid {C.T.LINE}">'
                        f'<div style="font-size:13px;color:{C.T.INK}">{C.chip(r["channel"] or "—", "info")} '
                        f'{C.esc(r["question"])}</div>'
                        f'<div style="font-size:12px;color:{C.T.MUTED};margin-top:4px">'
                        f'{C.esc(ans[:90])} · {r["steps"]} 步</div></div>')
            else:
                st.caption("暂无会话。")

    with t1:
        if not s["order"]:
            st.info("暂无会话。到『问答入口』提一个问题，即可在此按会话回放每一步。")
        else:
            sid = st.selectbox("选择会话", s["order"][::-1])
            ss = D.session_steps(sid, steps)
            head = ss[0] if ss else {}
            C.html(
                f'<div style="margin:6px 0 14px">'
                f'<div class="dm-h">{C.esc(head.get("question", ""))}</div>'
                f'<div style="margin-top:6px">{C.chip("通道 " + (head.get("channel") or "—"), "info")} '
                f'{C.chip(str(len(ss)) + " 步")} {C.chip(sid)}</div></div>')
            with C.card():
                C.timeline(_timeline_items(ss))

    with t2:
        st.caption("在此提问 = 调用同一个 Claude 智能体 + MCP 连接器；每一步都会留痕（见『任务链回放』『访问治理』）。")
        if "chat_q" not in st.session_state:
            st.session_state.chat_q = ""
        cols = st.columns(len(_EXAMPLES))
        for i, ex in enumerate(_EXAMPLES):
            if cols[i].button(f"示例 {i + 1}", help=ex, key=f"ex{i}", use_container_width=True):
                st.session_state.chat_q = ex
        q = st.text_input("问点什么？", value=st.session_state.chat_q,
                          placeholder="例：物料 M0001 现在总库存多少？分布在哪些仓库？")
        if st.button("提问", type="primary") and q.strip():
            from dm.agent import run_agent
            with st.spinner("智能体思考中（经 MCP 连接器查仓库，可能十几秒到一两分钟）…"):
                r = run_agent(q.strip(), channel="mgmt")
            st.markdown("#### 答案")
            C.html(C.answer_card(r["answer"]))
            st.caption(f'会话 {r["session_id"]} · 可在『任务链回放』看每一步')
            new_steps = [x for x in read_log("agent_session") if x["session_id"] == r["session_id"]]
            with st.expander(f"任务链（{len(new_steps)} 步）", expanded=True):
                C.timeline(_timeline_items(new_steps))
