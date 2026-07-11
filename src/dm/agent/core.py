"""数据平台智能体（默认：自研 LangGraph + 本地 LLM 网关；保留 claude -p 旧路径可回切）。

默认实现（DM_AGENT_IMPL=langgraph）：LangGraph StateGraph 进程内直调治理内核
（dm/tools：PBAC/审计/脱敏一处强制），LLM 走 OpenAI 兼容网关（LiteLLM→ollama 本地模型，
数据不出域；云端备选在网关配置切换）。任务链/审计/推送契约与 claude -p 时代逐字一致。

回切（DM_AGENT_IMPL=claude）：沿用旧无头 `claude -p` + stdio MCP 子进程路径（依赖本机
已登录的 claude CLI）。留作行为对拍与应急退路。

用法:
  dm-agent "物料 M0001 现在总库存多少？分布在哪些仓库？"
也可被通道/eval 调用: from dm.agent import run_agent（可传 on_step 回调实现"边做边发"）
"""
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from dm.agent.prompts import NUDGE, SYSTEM  # noqa: F401  (SYSTEM 供外部引用兼容)
from dm.config import DATA_DIR, resolve_claude
from dm.schema import TABLES
from dm.warehouse.store import LOG_DIR, append_log, read_log

# MCP 子进程在未 `pip install -e .` 时兜底导入 dm：指向 src/ 目录（claude 旧路径用）
SRC_DIR = Path(__file__).resolve().parent.parent.parent
# 嵌入模型缓存目录：父进程算好显式注入子进程 + HF 离线（防联网卡死）——两条路径共用
_EMBED_CACHE = str(Path.home() / ".cache" / "dm_fastembed")

MIN_INTERVAL = 0.7  # 钉钉发消息节流：相邻两条至少间隔这么久，避免被限流/漏发


# 表英文名→中文名（意图行用；schema 是单一真相源。dbt 分层表 dm_dw.* 不在其中→显示原名）
_TABLE_CN = {t["name"]: t["cn"] for t in TABLES}
# 抽 SQL 里被查的表：FROM/JOIN 后的裸标识符（够用即可，CTE 别名误抽也只是多一个原名标签）
_SQL_TABLE_RE = re.compile(r"\b(?:FROM|JOIN)\s+`?([A-Za-z_][\w.]*)`?", re.IGNORECASE)
_GRAPH_MODE_CN = {"find_related": "找关联实体", "impact_path": "查影响链路", "cypher": "图查询"}


def _table_label(name: str) -> str:
    cn = _TABLE_CN.get(name)
    return f"【{cn}】" if cn else f"【{name}】"


def _fmt_tool(name: str, inp: dict) -> str:
    """把一次工具调用格式化成业务用户看得懂的中文意图行（钉钉推送用；不再出现 SQL/JSON 原文，
    原始参数仍完整落审计日志供回放页调试）。"""
    name = (name or "").split("__")[-1]  # mcp__dm__run_sql -> run_sql（两路径兼容）
    inp = inp or {}
    if name == "run_sql":
        tables = list(dict.fromkeys(_SQL_TABLE_RE.findall(inp.get("sql", ""))))
        if tables:
            return "🔍 正在查询" + "".join(_table_label(t) for t in tables[:6]) + "…"
        return "🔍 正在执行数据查询…"
    if name == "describe_table":
        t = inp.get("name", "")
        cn = _TABLE_CN.get(t)
        return f"🔍 查看表【{cn} {t}】的结构" if cn else f"🔍 查看表【{t}】的结构"
    if name == "list_tables":
        return "🔍 我先看看数据仓库里有哪些表"
    if name == "search_documents":
        return f"📄 检索相关文档：{inp.get('query', '')}"
    if name == "graph_query":
        mode = inp.get("mode", "")
        tgt = inp.get("entity_id", "") or str(inp.get("cypher", ""))[:40]
        return f"🕸️ 在知识图谱里{_GRAPH_MODE_CN.get(mode, mode)}：{tgt}"
    if name == "list_metrics":
        return "📐 查看已注册的指标口径"
    if name == "query_metric":
        return f"📐 按注册口径取数：{inp.get('metric', '')}"
    if name == "execute_action":
        return f"🛠️ 准备执行治理动作：{inp.get('action', '')}（默认需人工审批）"
    return f"🔧 {name}"


def _fmt_receipt(name: str, res) -> str:
    """工具执行完立刻给用户的短回执（钉钉推送用）：报进展、错误/权限拦截必须如实可见。
    describe/list 类成功时返回空串（意图行已足够，避免刷屏）；细节全量在审计日志。"""
    name = (name or "").split("__")[-1]
    s = str(res or "").strip()
    data = None
    if s[:1] in "{[":
        try:
            data = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            data = None
    # 错误与权限拦截优先、必须如实可见。文案取 error 字段或纯文本首行——
    # 内核失败常返回美化 JSON（首行只有 "{"），绝不能拿原文首行当回执
    err = ""
    if isinstance(data, dict) and data.get("error"):
        err = str(data["error"]).splitlines()[0]
    elif data is None and (s.startswith("⛔") or s.startswith("ERROR") or "权限不足" in s[:200]):
        err = s.splitlines()[0]
    if err:
        if "权限" in err:
            return err[:120] if err.startswith("⛔") else f"⛔ {err[:110]}"
        return "⚠️ 这一步执行出错了，我调整一下再试"
    if name == "run_sql":
        n = data.get("row_count") if isinstance(data, dict) else None
        return f"✅ 查到 {n} 行数据，正在分析…" if isinstance(n, int) else "✅ 查询完成，正在分析…"
    if name == "search_documents":
        n = len(data) if isinstance(data, list) else None
        return f"✅ 找到 {n} 篇相关文档，正在阅读…" if isinstance(n, int) else "✅ 文档检索完成，正在阅读…"
    if name == "graph_query":
        return "✅ 图谱关系已返回，正在梳理…"
    if name == "query_metric":
        return "✅ 指标数值已取到，正在核对…"
    if name == "execute_action":
        if isinstance(data, dict) and data.get("status") == "pending_approval":
            return "📝 已生成待审批预览（未真正写库，需人工审批后生效）"
        if isinstance(data, dict) and data.get("ok"):
            return "✅ 治理动作已执行"
        return "⚠️ 治理动作未能提交，我看看原因"
    return ""  # describe_table / list_tables / list_metrics 等：意图行已说明，成功即静默


def run_agent(question: str, channel: str = "cli", model: str | None = None, on_step=None,
              role: str | None = None, user: str | None = None, purpose: str | None = None) -> dict:
    sid = "S" + datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
    # 权限主体：角色/用户/目的（PBAC）——LangGraph 路径显式随 Principal 传；claude 旧路径经 env 注入
    _role = role or os.environ.get("DM_ROLE", "仓管")
    _user = user or os.environ.get("DM_USER", "agent")
    _purpose = purpose or os.environ.get("DM_PURPOSE", "")

    if os.environ.get("DM_AGENT_IMPL", "langgraph").strip().lower() == "claude":
        return _run_agent_claude(question, channel, model, on_step, sid, _role, _user, _purpose)

    # ---------------- 默认：LangGraph + 治理内核（进程内） ----------------
    from dm.tools import Principal
    principal = Principal(user=_user, role=_role, purpose=_purpose, session_id=sid,
                          channel=channel, warehouse_id=os.environ.get("DM_WAREHOUSE", ""))

    state = {"step": 0, "last_emit": 0.0, "last_msg": ""}

    def log(stype, content, final_answer=""):
        state["step"] += 1
        append_log("agent_session", {
            "session_id": sid, "ts": datetime.now().isoformat(timespec="seconds"),
            "channel": channel, "question": question, "step_no": state["step"],
            "step_type": stype, "content": content, "final_answer": final_answer,
        })

    def emit(msg):
        """把一步过程实时推给调用方（如钉钉边做边发）；带轻节流。on_step 为空则什么都不做。"""
        if not on_step or not msg or not msg.strip():
            return
        wait = MIN_INTERVAL - (time.monotonic() - state["last_emit"])
        if wait > 0:
            time.sleep(wait)
        try:
            on_step(msg.strip())
        except Exception:  # noqa: BLE001
            pass
        state["last_emit"] = time.monotonic()
        state["last_msg"] = msg.strip()

    log("question", question)
    try:
        from dm.agent.graph import run_graph
        final = run_graph(question, principal, model, log, emit, _fmt_tool, _fmt_receipt) or "(无最终结果)"
    except Exception as e:  # noqa: BLE001  网关不可达等：如实报错，不臆造
        final = f"(无最终结果) 智能体执行失败：{str(e)[:300]}"
        log("plan", final)
    # 兜底：若最终结论没有作为最后一条推送发出，补发一条，避免调用方漏掉结论
    if final.strip() and final.strip() not in state["last_msg"]:
        emit(final)
    log("answer", final, final_answer=final)
    return {"session_id": sid, "answer": final}


def _run_agent_claude(question: str, channel: str, model: str | None, on_step,
                      sid: str, _role: str, _user: str, _purpose: str) -> dict:
    """旧路径：无头 `claude -p` + stdio MCP 子进程（保留作应急回切与行为对拍）。"""
    cfg = {"mcpServers": {"dm": {
        "command": sys.executable, "args": ["-m", "dm.connector.mcp_server"],
        "env": {"DM_SESSION_ID": sid, "DM_CHANNEL": channel, "PYTHONUTF8": "1", "NO_PROXY": "*",
                "DM_DATA_DIR": str(DATA_DIR), "PYTHONPATH": str(SRC_DIR),
                "DM_USER": _user, "DM_ROLE": _role, "DM_PURPOSE": _purpose,
                "DM_EMBED_CACHE": _EMBED_CACHE, "HF_HUB_OFFLINE": "1",
                "HF_HUB_DISABLE_SYMLINKS": "1", "USERPROFILE": str(Path.home())},
    }}}
    cfg_path = LOG_DIR / f"mcpcfg_{sid}.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    base = [
        resolve_claude(), "-p",
        "--mcp-config", str(cfg_path), "--strict-mcp-config",
        # 显式放行连接器的 6 个 MCP 工具 + 禁用内置工具。切勿用 `--tools ""`——它会把 MCP 工具也一并禁掉，
        # 使智能体拿不到任何工具，退化成"只规划、不调用"（满屏 plan、审计为空、答案是编的）。
        "--allowedTools", "mcp__dm__list_tables,mcp__dm__describe_table,mcp__dm__run_sql,mcp__dm__search_documents,mcp__dm__graph_query,mcp__dm__execute_action",
        "--disallowedTools", "Bash,Read,Edit,Write,NotebookEdit,Glob,Grep,WebFetch,WebSearch,Task",
        "--permission-mode", "bypassPermissions",
        "--append-system-prompt", SYSTEM + f"\n（当前操作者角色：{_role}；越权访问会被连接器拒绝并记入审计。）",
        "--output-format", "stream-json", "--verbose",
    ]
    if model:
        base += ["--model", model]

    state = {"step": 0, "final": "", "claude_sid": "", "err": "", "last_text": "", "last_emit": 0.0}

    def log(stype, content, final_answer=""):
        state["step"] += 1
        append_log("agent_session", {
            "session_id": sid, "ts": datetime.now().isoformat(timespec="seconds"),
            "channel": channel, "question": question, "step_no": state["step"],
            "step_type": stype, "content": content, "final_answer": final_answer,
        })

    def emit(msg):
        if not on_step or not msg or not msg.strip():
            return
        wait = MIN_INTERVAL - (time.monotonic() - state["last_emit"])
        if wait > 0:
            time.sleep(wait)
        try:
            on_step(msg.strip())
        except Exception:  # noqa: BLE001
            pass
        state["last_emit"] = time.monotonic()

    env = {**os.environ, "PYTHONUTF8": "1"}

    def run_once(cmd):
        """跑一次 claude -p，把 stream-json 解析成任务链；返回本轮是否真的调用过工具。"""
        saw_tool = False
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                errors="replace", env=env)
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("session_id"):
                state["claude_sid"] = ev["session_id"]   # 供 --resume 续接同一会话
            t = ev.get("type")
            if t == "assistant":
                parts = []  # 同一条 assistant 消息的文本+工具调用合并成一条推送
                for blk in ev.get("message", {}).get("content", []):
                    if blk.get("type") == "text" and blk.get("text", "").strip():
                        txt = blk["text"].strip()
                        log("plan", txt)
                        state["last_text"] = txt
                        parts.append(txt)
                    elif blk.get("type") == "tool_use":
                        saw_tool = True
                        args = json.dumps(blk.get("input", {}), ensure_ascii=False)
                        log("tool_call", f'{blk.get("name", "")}  {args}')
                        parts.append(_fmt_tool(blk.get("name", ""), blk.get("input", {}) or {}))
                if parts:
                    emit("\n\n".join(parts))
            elif t == "user":
                for blk in ev.get("message", {}).get("content", []):
                    if isinstance(blk, dict) and blk.get("type") == "tool_result":
                        c = blk.get("content", "")
                        if isinstance(c, list):
                            c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
                        log("tool_result", str(c)[:2000])
            elif t == "result":
                state["final"] = ev.get("result", "") or ""
        proc.wait()
        state["err"] = (proc.stderr.read() or "").strip()
        return saw_tool

    nudge = NUDGE
    try:
        log("question", question)
        # 外层重试：高负载下 claude -p 偶发 MCP 握手失败（工具未注册 → 模型把工具调用当文本写出、不查证）。
        # 一整轮都没真正调用过任何工具时，**全新** claude -p 重跑（重新握手），最多 3 轮。
        saw = False
        for attempt in range(3):
            if attempt > 0:
                state["claude_sid"] = ""
                state["final"] = ""
                log("plan", f"（疑似 MCP 工具未注册/未触发，第 {attempt} 次全新会话重试）")
            saw = run_once(base + [question])
            # 兜底：模型只写了计划却没调用工具时，续接同一会话催它真正执行。最多催 2 次。
            tries = 0
            while not saw and tries < 2 and state["claude_sid"]:
                tries += 1
                log("plan", f"（自动续跑#{tries}：只给了计划未查证，系统催办）{nudge}")
                saw = run_once(base + ["--resume", state["claude_sid"], nudge])
            if saw:
                break

        if not state["final"]:
            state["final"] = f"(无最终结果) {state['err'][:500]}" if state["err"] else "(无最终结果)"
        # 兜底：若最终结论没有作为最后一段叙述流式发出（少见），补发一条，避免漏掉结论
        if state["final"].strip() and state["final"].strip() != state["last_text"].strip():
            emit(state["final"])
        log("answer", state["final"], final_answer=state["final"])
    finally:
        try:
            cfg_path.unlink()
        except OSError:
            pass
    return {"session_id": sid, "answer": state["final"]}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    q = " ".join(sys.argv[1:]).strip() or "物料 M0001 现在总库存多少？分布在哪些仓库？"
    print(f"问题: {q}\n（智能体思考中，可能需要十几秒到一两分钟…）\n")
    r = run_agent(q)
    steps = [s for s in read_log("agent_session") if s["session_id"] == r["session_id"]]
    print(f"会话 {r['session_id']} 共 {len(steps)} 步:")
    for s in steps:
        print(f"  [{s['step_no']}] {s['step_type']}: {str(s['content'])[:90]}")
    print(f"\n===== 答案 =====\n{r['answer']}")


if __name__ == "__main__":
    main()
