"""LangGraph 智能体图：规划/ReAct 工具循环/终答，治理内核进程内直调。

图结构：
    START → agent ──(有 tool_calls)──→ tools → agent   （ReAct 循环）
                └──(无工具且从未查证，≤2 次)──→ nudge → agent   （催办，对齐旧 claude 路径的续跑兜底）
                └──(其余)──→ END

留痕契约（与 claude -p 时代逐字对齐，管理平台回放零改动）：
    模型叙述/思考 → step_type=plan；每个工具调用 → tool_call（"name  {json}"）；
    工具返回 → tool_result（截断 2000）；终答由 core.run_agent 记 answer。
检查点：langgraph-checkpoint-postgres 存我们自己的 PG（thread_id=会话 sid）；
PG 不可达自动降级内存检查点（检查点非验收硬项，绝不因它挡主流程）。
"""
import json
import threading
import time

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.utils import message_chunk_to_message
from langchain_core.tools import tool as lc_tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

from langgraph.graph.message import add_messages

from dm import tools as kernel
from dm.agent.prompts import NUDGE, SYSTEM
from dm.config import (ANCHOR_TODAY, CKPT_PG_URL, LLM_API_KEY, LLM_BASE_URL,
                       LLM_CONNECT_TIMEOUT, LLM_MAX_TOKENS, LLM_MODEL, LLM_READ_TIMEOUT,
                       LLM_STREAMING, LLM_WALL_TIMEOUT)

RECURSION_LIMIT = 25

_CKPT = None
_CKPT_LOCK = threading.Lock()


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    saw_tool: bool
    nudges: int


def _checkpointer():
    """PG 检查点（连接池）→ 单连接 → 内存，三级降级；进程内单例。"""
    global _CKPT
    if _CKPT is not None:
        return _CKPT
    with _CKPT_LOCK:
        if _CKPT is not None:
            return _CKPT
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg_pool import ConnectionPool
            pool = ConnectionPool(CKPT_PG_URL, min_size=1, max_size=4, timeout=5,
                                  kwargs={"autocommit": True, "prepare_threshold": 0},
                                  open=True)
            saver = PostgresSaver(pool)
            saver.setup()
            _CKPT = saver
        except Exception:  # noqa: BLE001  PG 不可达/依赖缺失 → 内存检查点
            from langgraph.checkpoint.memory import MemorySaver
            _CKPT = MemorySaver()
    return _CKPT


def _trivial(t: str) -> bool:
    """终答是否"没内容"（空/纯省略号标点——思考型模型的塌缩输出）。"""
    return len(t.strip().strip(".。…‥⋯·、,，!！?？ \n\t")) < 3


def _invoke_llm(runnable, msgs):
    """一次 LLM 调用。默认流式：逐 chunk 聚合 + 墙钟上限，超时/异常即关闭生成器——
    连接断开经网关传导到推理后端，生成当场中止、并发槽立即释放（僵尸根治，DEVLOG 坑27）。
    AIMessageChunk 相加自动合并 tool_call_chunks 与 reasoning 增量，终转 AIMessage 后
    下游 `ai.tool_calls` / `additional_kwargs.reasoning_content` 的读取与非流式完全一致。
    DM_LLM_STREAMING=0 走与旧版逐字一致的非流式 invoke（应急回退）。"""
    if not LLM_STREAMING:
        return runnable.invoke(msgs)
    agg = None
    deadline = time.monotonic() + LLM_WALL_TIMEOUT
    gen = runnable.stream(msgs)
    try:
        for chunk in gen:
            agg = chunk if agg is None else agg + chunk
            if time.monotonic() > deadline:
                raise TimeoutError(f"LLM 单次调用超墙钟 {LLM_WALL_TIMEOUT:.0f}s，已断开连接止损")
    finally:
        gen.close()
    if agg is None:
        raise RuntimeError("LLM 流式响应为空")
    return message_chunk_to_message(agg)


def _reasoning_of(msg) -> str:
    """思考型模型的推理文本。字段名因链路而异：LiteLLM 网关=reasoning_content，
    ollama /v1 直连=reasoning（主链路已直连——LiteLLM 对客户端断开不取消上游，
    是"取消黑洞"，僵尸根治要求断开一跳直达推理后端，DEVLOG 坑29）。"""
    kw = getattr(msg, "additional_kwargs", None) or {}
    return str(kw.get("reasoning_content") or kw.get("reasoning") or "").strip()


def _text_of(content) -> str:
    """AIMessage.content 可能是 str 或内容块列表——统一取纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in content
            if not isinstance(b, dict) or b.get("type") in (None, "text")
        ).strip()
    return str(content or "")


def _make_tools(principal):
    """把治理内核函数包成 LangChain 工具（工具名/参数/docstring 与 MCP 完全同名同参，
    审计 tool_name 一致）。principal 经闭包注入，不出现在模型可见的参数里。"""

    @lc_tool
    def list_tables() -> str:
        """列出数据仓库里所有业务表（表英文名、中文名、说明、行数）。建议先调用它了解有哪些数据。"""
        return kernel.list_tables(principal)

    @lc_tool
    def describe_table(name: str) -> str:
        """查看某张表的字段定义：列名、类型、中文名、是否主键、外键指向。参数 name 为表英文名。"""
        return kernel.describe_table(principal, name)

    @lc_tool
    def run_sql(sql: str) -> str:
        """对数据仓库执行只读 SELECT 查询并返回结果（最多 200 行，JSON）。
        仅允许单条 SELECT / WITH 查询；任何写操作、DDL、多语句都会被拒绝。
        表结构请先用 list_tables / describe_table 获取。"""
        return kernel.run_sql(principal, sql)

    @lc_tool
    def search_documents(query: str, top_k: int = 5) -> str:
        """检索非结构化文档库（采购合同 / 作业指导书SOP / 进货检验质检报告 / 设备维护手册 / 物料技术规格书）。
        当问题涉及『文档里才有』的内容时用它做语义检索，例如：合同条款（账期/违约金/质保）、
        工艺与作业 SOP（工序/公差/关键设备）、设备维护周期与报警码、质检结论与不良率、物料技术规格（材质/存储/保质期）。
        参数：query 自然语言问题（可含物料/供应商/到货等 ID 以精确定位）；top_k 返回片段数（默认 5）。
        返回 JSON 数组，每条含 doc_id / doc_type / title / entities(关联实体ID) / chunk_no / score / content。
        请据返回片段作答并标注出处（文档标题或 doc_id）；若片段中查不到答案，如实说明『文档未提及』，不要臆造。"""
        return kernel.search_documents(principal, query, top_k)

    @lc_tool
    def graph_query(mode: str, entity_id: str = "", target_type: str = "",
                    max_hops: int = 3, cypher: str = "", limit: int = 30) -> str:
        """知识图谱查询（实体关系层 = 结构化外键骨架 + 文档抽取的新关系，存于 Neo4j）。三种 mode：
        - find_related：找与 entity_id（如供应商 S001 / 物料 M0001 / 设备 CNC-08）max_hops 跳内相连的实体与关系——跨域链接发现。
        - impact_path：从 entity_id 到 target_type（如 Customer / SalesOrder / Material / Document）的最短路径——断供影响 / 质量溯源等多跳分析。
        - cypher：执行只读 Cypher（高级；写/管理操作被拒）。
        何时用：问『谁会被牵连/影响』『经由哪些环节关联』『上下游链路』『跨结构化+文档的关系』等图式问题。
        返回 JSON（find_related→related[]；impact_path→paths[]含 path 节点链；cypher→rows[]）。常与 run_sql / search_documents 组合作答。"""
        return kernel.graph_query(principal, mode, entity_id, target_type, max_hops, cypher, limit)

    @lc_tool
    def list_metrics() -> str:
        """列出全部业务指标定义（名称/中文名/口径说明/允许维度/单位/负责人）。回答口径类问题先看这里。"""
        return kernel.list_metrics(principal)

    @lc_tool
    def query_metric(metric: str, dimensions: str = "", filters: str = "", limit: int = 100) -> str:
        """按注册口径查询业务指标数值（缺料物料数/净需求/可发货量/库存总量/采购在途量/销售额）。
        参数：metric 指标名（先用 list_metrics 查可用项）；dimensions 逗号分隔的分组维度（可空）；
        filters 分号分隔的过滤（形如 material_id='M0001'；只接受简单比较）；limit 行数上限。
        返回 JSON：{metric, cn, sql, columns, rows}。涉敏指标受 Marking/PBAC 约束，无权会被拒。"""
        return kernel.query_metric(principal, metric, dimensions, filters, limit)

    @lc_tool
    def execute_action(action: str, material_id: str = "", new_value: int = 0,
                       supplier_id: str = "", qty: int = 0, so_id: str = "",
                       approve: bool = False) -> str:
        """执行一次**治理化写回 Action**（会改源系统数据，受写回权限约束、全程留审计、可回滚）。支持：
        - adjust_safety_stock(material_id, new_value)：调整物料安全库存阈值
        - create_purchase_requisition(material_id, supplier_id, qty)：生成采购申请
        - create_delivery(so_id, qty)：发起发货（**提交条件：现有库存≥qty**，不足会被拒）
        默认 approve=False 只返回『待审批预览』(不写库)；需人工在审批台批准、或明确 approve=True 才真正写回。
        仅当用户明确要求执行上述写操作时使用；只读查询一律用 run_sql。
        返回 JSON：ok / status(pending_approval) / preview / message / error。权限不足或提交条件不满足会被拒。"""
        return kernel.execute_action(principal, action, material_id, new_value, supplier_id, qty, so_id, approve)

    return [list_tables, describe_table, run_sql, search_documents, graph_query,
            list_metrics, query_metric, execute_action]


def run_graph(question: str, principal, model: str | None, log, emit, fmt_tool, fmt_receipt=None) -> str:
    """跑一轮智能体图，返回最终答案文本。log/emit/fmt_tool/fmt_receipt 由 core.run_agent 注入（留痕与推送契约）。"""
    fmt_receipt = fmt_receipt or (lambda name, res: "")
    tools = _make_tools(principal)
    dispatch = {t.name: t for t in tools}
    # 流式下 httpx 的 read 超时=相邻 token 间隔上限；非流式回退时单标量=整次响应上限。
    # max_retries=1：流式+分层超时后重试收益低，并发场景防重试风暴放大排队。
    timeout = (httpx.Timeout(connect=LLM_CONNECT_TIMEOUT, read=LLM_READ_TIMEOUT,
                             write=30.0, pool=10.0) if LLM_STREAMING else LLM_WALL_TIMEOUT)
    # max_tokens：思考型模型遇开放分析题会失控长写（实测单步 4 分钟撞墙钟）——生成侧设上限，
    # 与墙钟(时间侧)双保险；thinking 吃满导致终答为空时由"塌缩兜底"追加收尾调用。
    llm = ChatOpenAI(model=model or LLM_MODEL, base_url=LLM_BASE_URL, api_key=LLM_API_KEY,
                     temperature=0.6, timeout=timeout, max_retries=1, max_tokens=LLM_MAX_TOKENS)
    llm_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState):
        ai: AIMessage = _invoke_llm(llm_tools, [SystemMessage(content=_system(principal))] + state["messages"])
        parts = []
        reasoning = _reasoning_of(ai)
        text = _text_of(ai.content).strip()
        if reasoning and not text:
            # 思考型模型：叙述在 reasoning 里——入回放（plan），推送截断避免钉钉刷屏
            log("plan", reasoning[:2000])
            parts.append(reasoning[:400])
        if text:
            log("plan", text)
            parts.append(text)
        for tc in (ai.tool_calls or []):
            args_json = json.dumps(tc.get("args") or {}, ensure_ascii=False)
            log("tool_call", f'{tc["name"]}  {args_json}')
            parts.append(fmt_tool(tc["name"], tc.get("args") or {}))
        if parts:
            emit("\n\n".join(p for p in parts if p))
        return {"messages": [ai], "saw_tool": state["saw_tool"] or bool(ai.tool_calls)}

    def tools_node(state: AgentState):
        last = state["messages"][-1]
        outs = []
        receipts = []
        for tc in (last.tool_calls or []):
            fn = dispatch.get(tc["name"])
            try:
                res = fn.invoke(tc.get("args") or {}) if fn else f'ERROR: 未知工具 {tc["name"]}'
            except Exception as e:  # noqa: BLE001  参数不合法等 → 把报错还给模型自行修正
                res = f"ERROR: 工具执行失败: {e}"
            log("tool_result", str(res)[:2000])
            receipts.append(fmt_receipt(tc["name"], res))
            outs.append(ToolMessage(content=str(res), tool_call_id=tc.get("id") or tc["name"], name=tc["name"]))
        # 执行完立刻回执（同批合并一条）：错误/权限拦截必须让用户可见，
        # 且下一轮 LLM 推理可长达数十秒~数分钟，这是唯一能填补静默的进度信号
        emit("\n".join(dict.fromkeys(r for r in receipts if r)))
        return {"messages": outs}

    def nudge_node(state: AgentState):
        n = state["nudges"] + 1
        log("plan", f"（自动续跑#{n}：只给了计划未查证，系统催办）{NUDGE}")
        return {"messages": [HumanMessage(content=NUDGE)], "nudges": n}

    def route(state: AgentState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        if not state["saw_tool"] and state["nudges"] < 2:
            return "nudge"
        return "end"

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.add_node("nudge", nudge_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", "nudge": "nudge", "end": END})
    g.add_edge("tools", "agent")
    g.add_edge("nudge", "agent")
    compiled = g.compile(checkpointer=_checkpointer())

    init: AgentState = {"messages": [HumanMessage(content=question)], "saw_tool": False, "nudges": 0}
    cfg = {"configurable": {"thread_id": principal.session_id}, "recursion_limit": RECURSION_LIMIT}
    try:
        final_state = compiled.invoke(init, cfg)
        msgs = final_state["messages"]
    except Exception as e:  # noqa: BLE001  递归上限/网关中断等：兜底取已有内容
        log("plan", f"（图执行中断：{str(e)[:200]}——以当前已知信息收尾）")
        return f"(无最终结果) {str(e)[:300]}"

    final = ""
    for m in reversed(msgs):
        if isinstance(m, AIMessage) and not m.tool_calls:
            text = _text_of(m.content).strip()
            if text and not _trivial(text):
                final = text
                break
            reasoning = _reasoning_of(m)
            if reasoning and not _trivial(reasoning):
                final = reasoning
                break
    if not final:
        # 思考型模型偶发把终答塌缩成省略号（内容全在 reasoning）——追加一次无工具收尾调用
        try:
            wrap = _invoke_llm(llm, [SystemMessage(content=_system(principal))] + msgs + [HumanMessage(
                content="请基于以上全部查证结果，用中文给出简洁的最终答复（包含关键数字与结论），不要再调用工具。")])
            final = _text_of(wrap.content).strip() or _reasoning_of(wrap)
            if final:
                log("plan", "（终答塌缩，已追加收尾调用生成最终答复）")
        except Exception:  # noqa: BLE001
            pass
    return final or "(无最终结果)"


def _system(principal) -> str:
    s = SYSTEM + f"\n（当前操作者角色：{principal.role}；越权访问会被连接器拒绝并记入审计。）"
    if ANCHOR_TODAY:
        s += (f"\n（数据日期锚：本环境业务数据的“今天”固定为 {ANCHOR_TODAY}。用户问题中的"
              "今天/明天/昨天/本周/上月等相对时间一律以该日期推算；不要用 CURRENT_DATE() 或系统时间，"
              "它们与业务数据不同步。）")
    return s
