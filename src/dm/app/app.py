"""Streamlit 管理平台 = 数据治理平台 + 智能体的运行驾驶舱（浅色商务蓝）。

双层导航：侧栏 6 大模块 + 每模块顶部子标签。
重点是「我们交付的这套东西」的运行状况：智能体每一步、MCP 访问治理、实时同步（Flink CDC）、
Eval 质量、数仓健康——而非客户业务数据。每个模块独立 graceful 渲染，单模块出错不拖垮全站。
运行: dm-app
"""
import streamlit as st

from dm.app import theme as T
from dm.app.pages import (
    actions_page, agent, catalog_page, control_panel, dashboard, docs, governance, graph,
    health_page, lineage_page, metrics_page, ontology_page, quality, reports_page,
    security_page, sync, warehouse, workshop,
)
from dm.config import FLINK_URL, WH_DB, WH_HOST, WH_PORT

st.set_page_config(page_title="DataSteward 数据治理台", page_icon="🏭", layout="wide")
T.inject_css()

MODULES = [
    ("🚀 运行驾驶舱", dashboard.render, "平台与智能体的一眼总览"),
    ("🛰️ 管理者面板", control_panel.render, "平台运维单一视图：清单 · 权限 · 资源 · 活动审计"),
    ("🔄 实时同步监控", sync.render, "Postgres → Flink CDC → StarRocks 实时管道"),
    ("🩺 数据健康", health_page.render, "监控目录 + 阈值告警：新鲜度/量/期望/源汇对账/结构"),
    ("🧠 智能体", agent.render, "活动总览 · 任务链回放 · 问答入口"),
    ("🛡️ 访问治理", governance.render, "MCP 每次工具调用全程留痕、可审计"),
    ("🔐 权限与 Markings", security_page.render, "两层安全：强制 Markings AND 自主角色 + 行列 + 写回权限"),
    ("⚡ Action 审批台", actions_page.render, "治理化写回：发起 → 审批 → 写回 PG → 可回滚"),
    ("🛠️ 操作台 Workshop", workshop.render, "操作型应用：缺料→采购申请 / 可发货→发起发货（任务队列）"),
    ("✅ 质量 Eval", quality.render, "通过率 · 趋势 · 按类别 · 逐条红绿"),
    ("📊 报表", reports_page.render, "管理者仪表盘 + 字段级业务报表（库存/缺料/采购/销售）"),
    ("🗄️ 数据仓库", warehouse.render, "19 张业务表总览与详情"),
    ("📇 数据目录", catalog_page.render, "L9 目录：业务表 + DW 分层 + 指标口径 + Marking 传播，一处检索"),
    ("📏 指标字典", metrics_page.render, "L6 指标层：注册口径一览 + 试算（智能体/报表/eval 同源）"),
    ("🧩 本体 Ontology", ontology_page.render, "对象/属性/链接 + Object Explorer + 可用 Action"),
    ("🧬 血缘 Lineage", lineage_page.render, "raw/refined 分层 + 端到端血缘 + 列级 + 安全随血缘传播"),
    ("📚 文档知识库", docs.render, "合成文档 → 本地嵌入 bge → pgvector 语义检索（RAG）"),
    ("🕸️ 知识图谱", graph.render, "实体关系层：跨域链接 + 多跳影响/溯源（Neo4j）"),
]
labels = [m[0] for m in MODULES]

with st.sidebar:
    st.markdown('<div class="dm-brand">🏭 DataSteward 数据治理台</div>', unsafe_allow_html=True)
    choice = st.radio("模块", labels, label_visibility="collapsed")
    st.markdown(
        f'<div class="dm-side-foot">数仓 · StarRocks<br>{WH_HOST}:{WH_PORT}/{WH_DB}<br><br>'
        f'实时同步 · Flink CDC<br>{FLINK_URL.replace("http://", "")}</div>',
        unsafe_allow_html=True)

label, render, desc = next(m for m in MODULES if m[0] == choice)
st.markdown(
    f'<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:10px">'
    f'<span class="dm-h" style="font-size:22px">{label}</span>'
    f'<span class="dm-muted">{desc}</span></div>',
    unsafe_allow_html=True)

try:
    render()
except Exception as e:  # noqa: BLE001  —— 单模块 graceful：不让一个模块的异常拖垮整站
    st.error(f"该模块渲染出错：{e}")
    st.exception(e)
