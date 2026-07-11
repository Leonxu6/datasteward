# 数据平台设计与验收（含 v2 十层重构）

## v2：十层现代数据栈重构 + GB10 生产化（2026-07-07，PR #27-#33）

**已落地**：L1 U8 接入路径（仿真库全链演练+接入需求清单，真库改 4 个 env 即切）｜L2 Flink CDC + U8 批抽增量水位｜L3 StarRocks(aarch64)｜L4 ELT（dbt 驱动 StarRocks 算力）｜L5 dbt ODS→DWD→DWS→ADS（15 模型+tests，anchor_today=2026-06-25）｜L6 指标注册表（6 指标口径唯一，query_metric 工具化）｜L7 Dagster（43 资产/调度/健康钉钉告警 sensor）｜L8 钉钉 ChatBI + Streamlit(18 页)｜L9 dbt tests 入健康页+数据目录页+Marking 沿 dbt 血缘传播+logrotate+OpenMetadata(尽力项)｜L10 **自研 LangGraph 智能体**（治理内核 dm/tools 8 工具进程内直调，MCP 壳对外；LiteLLM→ollama qwen3.6 本地 GPU 推理，DM_AGENT_IMPL=claude 可回切）。

**v2 验收基线**：smoke.sh 13/13；pytest 28 过；V1-V8 真实入口旅程（钉钉多跳/审批回滚/eval/权限对抗/CDC 顿挫/指标三算一致/提交条件拒绝/外部 MCP）全过。**二期清单**：SQL Server CDC 实时化、多智能体 supervisor、Cube 语义层服务、Langfuse 追踪、MDM（U8↔合成主数据对齐）、应用镜像 CI/CD、Superset 自助 BI、群 webhook 告警（待用户提供）。

---

# v1：最小可见 + 可审计 + 可评测的数据平台闭环 PoC

## Context（为什么做这件事）

- **背景**：全新项目（启动时只有一次需求会议的转写 + 一份接口文档，无任何代码）。目标是为一家制造业企业（已匿名化）做一个"轻量化工业软件平台"，第一步是把其某个数据源（MES / ERP-U8 等）的数据导入**统一数据平台/数据仓库**，并做一个 **connector** 让**智能体统一访问**。
- **接口文档关键事实**：那份接口文档是 MES 厂商给该企业做的 **MES↔ERP(用友U8)** 对接确认清单。它确认了 **19 类基础数据 + 23 个读写业务流程的范围**，但**每张表的字段映射全是空的**——没有字段级 schema、没有端点地址、没有 DDL。→ 所以今天**用合成数据**（按真实实体结构造），不依赖任何真实库/网络/接口。
- **今天的目标**：做一个**最小但端到端、看得见、留得下痕迹、跑得了评测**的闭环 PoC，验证这套架构跑得通，并能"测—诊断—修"，然后再和团队讨论扩展。

## 今天的"完成"定义（验收标准，可度量）

1. **导入成功 + 仓库可见**：19 张表**全部**成功入库；管理平台能看到每张表的**行数、字段、可预览数据**；合成数据**内部一致**（外键有效、演示/eval 问题都有确定解）。
2. **统一访问 + 全程留痕**：智能体**只能经 MCP 连接器**访问数据（不能绕过）；**每一步**（问题 → 计划 → 每步 SQL → 命中哪些表 → 返回行数 → 最终答案）都写审计；管理平台能**完整回放任一会话的任务链**。
3. **Eval 集合可跑可判分**：有一个 **eval 题集**（覆盖 直查 / 多表 / 多步任务链 / 越界问题）；**一条命令**跑完整个集合、**自动判分**、输出**通过率 + 逐条红绿**；确定性问题用仓库算出的标准答案自动比对，叙述型用 LLM 评判。**目标：确定性用例全过；越界用例智能体正确说"没有该数据"而不编造。**
4. **钉钉双向可测**：在钉钉网页发消息提问 → 收到答案；该会话同步出现在管理平台。
5. **可调试**：当某条 eval 失败或钉钉答案不对时，能在管理平台**定位到任务链的哪一步出错**（错表 / 错 SQL / 错聚合 / 幻觉），形成"**测—诊断—修**"闭环。

## 已锁定的设计决策（grilling 结论）

| 维度 | 决策 |
|---|---|
| 数据来源 | **合成数据**，按真实实体结构造；读取层做成**可替换源适配器**（以后换 U8 直连/API，上层不动） |
| 仓库 | **DuckDB**（单文件、零配置、列式/OLAP，正合"读多分析为主"；以后可迁 Postgres/ClickHouse） |
| 实体范围 | 接口文档里的 **19 类基础数据全造** |
| 数据保真度 | **代表性字段 + 真实外键关系**，由**一份 schema 定义**同时驱动「建表 + 造数 + MCP 取 schema + eval 标准答案」 |
| 连接器 | **MCP 服务器**（只读工具），**每次工具调用自动写审计** |
| 智能体大脑 | 复用 **Claude**（`claude -p` 无头 / Claude Agent SDK），多步工具调用白送，复用现有 Claude 登录，**无需额外 API key** |
| 智能体入口 | **钉钉 Stream 模式双向**（用户自建内部应用拿 AppKey/Secret）；做成**可插拔通道**，key 未就绪时自动回退到 webhook 推送 + 管理平台聊天框 |
| 管理平台 | **Streamlit**：仓库视图 + 审计 + 任务链回放 + **Eval 跑批视图**（= 可观测/调试中心） |
| 测试 | **Eval 题集自动判分** + 钉钉网页人工探测，二者都把会话留痕汇入管理平台供诊断 |

## 架构

```
[源适配器] 合成数据(可换U8/API)
      │ 批量加载(ETL)
      ▼
[DuckDB 数据仓库]  warehouse.duckdb  (19业务表 + audit_log + agent_session + eval_run)
      ▲ 只读
      │
[MCP 连接器]  list_tables / describe_table / run_sql(只读)  ──每次调用写审计──┐
      ▲                                                                      │
      │ MCP                                                                  ▼
[Claude 智能体]  claude -p / Agent SDK，多步任务链                  [审计 / 任务链 / eval]
      ▲           ▲                                                          │
 通道 │           │ 批量评测                                                 ▼
[钉钉Stream双向]◄主入口   [Eval 跑批 run_eval]      [Streamlit 管理平台 = 可观测/调试中心]
[管理平台聊天框]◄兜底                                 仓库视图 + 审计 + 任务链回放 + Eval红绿
```

## 项目结构（v1 当时的单目录形态；现已演进为 src 布局，见仓库根 README）

```
schema.py            # 19实体的单一 schema 定义（列/类型/主键/外键）——驱动建表+造数+MCP+eval
generate.py          # 按 schema 用 faker 造内部一致的合成数据（源适配器接口，可替换）
load.py              # 建表 + 灌库到 warehouse.duckdb
warehouse.duckdb     # 仓库文件（业务表 + audit_log + agent_session + eval_run）
mcp_server.py        # MCP 连接器：list_tables/describe_table/run_sql(只读) + 审计
agent.py             # 接 MCP 的 Claude 智能体（claude -p / Agent SDK），可被 CLI/通道/eval 调用
eval/eval_set.yaml   # eval 题集：{id, question, category, expected, grader}
eval/run_eval.py     # 跑全集 → 判分 → 通过率+逐条结果（每条带 session_id）
channels/dingtalk.py # 钉钉通道：先 webhook 单向（必通），再 Stream 双向（需 key）
app.py               # Streamlit 管理平台（仓库 / 审计 / 任务链回放 / Eval 视图 / 聊天框）
requirements.txt
```

## 数据模型（19 实体，代表性字段 + 关系）

由 `schema.py` 一份定义驱动。关系示意：
- 维度/主数据：`物料分类体系` ← `物料信息` → `单位`（+ `单位转换率`）；`公司组织信息` ← `部门` ← `职员信息`；`供应商`、`客户`；`字典`(单据分类枚举)
- 库存：`仓库` ← `库位`；`即时库存信息` →(`物料`,`仓库`,`库位`)
- 单据：`采购单`→(`供应商`,`物料`)；`采购到货单`→`采购单`；`销售订单`→(`客户`,`物料`)；`发货单`→(`销售订单`,`客户`)；`生产订单`→`物料`；`生产订单用料分析表/子件清单`→(`生产订单`,`物料`)
- 合成数据**内部一致**：单据/库存引用的物料 id 真实存在且有库存行，保证演示/eval 问题可答、标准答案可由 SQL 算出。

## Eval 集合（系统化测试）

- 文件 `eval/eval_set.yaml`，每条 `{id, question, category, expected, grader}`。
- **类别覆盖**：
  - `direct` 单表直查 — 例："物料 M0001 现在总库存多少？分布在哪些仓库？"
  - `join` 多表 — 例："供应商 S001 有哪些未完成的采购单？"
  - `multistep` 多步任务链（"能否按时交货"的今日可落地子集）— 例："销售订单 SO0001 现在库存够不够发货？" → ①查订单要哪些物料及数量 →②查即时库存 →③比对报缺口。
  - `out_of_scope` 越界 — 例："某产线明天的排班/产能够吗？"（数据**不在** 19 表内，期望智能体明确说"无此数据"而非编造）。
- **判分 grader**：
  - `numeric`/`set`：用 SQL 从仓库**算出标准答案**自动比对（确定性、可靠）。
  - `llm_judge`：叙述型/多步结论，用一次 LLM 评判是否命中关键事实。
  - `refusal`：越界用例，检查是否正确拒答/说明数据缺失。
- `eval/run_eval.py`：逐条跑 agent → 判分 → 打印**通过率 + 逐条红绿**，每条记录其 `session_id`（可在管理平台回放）；失败高亮。

## 测试与调试闭环

1. **系统化**：跑 `run_eval.py` → 看通过率与失败用例。
2. **探索式**：在**钉钉网页**给机器人发各种消息找 bug。
3. **诊断**：任一失败/错答 → 打开**管理平台**，按 `session_id` 回放任务链，定位错在哪一步（错表/错 SQL/错聚合/幻觉/数据问题）。
4. **修复** → 回到 1，直到验收标准达成。

## 构建顺序（自底向上，带"保底"检查点）

> 原则：先把**看得见的闭环**做出来，钉钉双向放最后；任何一步卡住，前面成果都可独立演示。

- **M1（保底·必达）** `schema.py` + `generate.py` + `load.py` + `app.py` 仓库视图 → **验收 #1**。
- **M2** `mcp_server.py`：MCP 连接器，`list_tables`/`describe_table`/`run_sql`(强制 SELECT-only)；每次调用写 `audit_log`。
- **M3** `agent.py` 接 MCP，CLI 跑通演示问题；会话每步写 `agent_session`；`app.py` 增加**审计 + 任务链回放视图** → **验收 #2**。
- **M3.5** `eval/eval_set.yaml` + `eval/run_eval.py` + `app.py` **Eval 视图** → **验收 #3、#5**（可评测 + 可调试）。
- **M4（冲刺）** `channels/dingtalk.py`：先 **webhook 单向**(零审批·必通)，再 **Stream 双向**(需用户 key)；未就绪自动回退 → **验收 #4**。

## 技术栈 / 依赖（Python）

`duckdb`、`mcp`(Python SDK)、`streamlit`、`dingtalk-stream`、`faker`、`pyyaml`、`anthropic`/`claude-agent-sdk`(或直接 shell 调 `claude -p`)。
> 各 SDK 的确切 API（MCP server、Agent SDK、钉钉 Stream）在构建时按官方文档逐一确认。

## 仓库内的留痕 / 评测表

- `audit_log`：id, ts, session_id, channel, user, tool_name, tool_args(JSON), sql, tables_touched, row_count, duration_ms, ok, error
- `agent_session`：session_id, ts, channel, question, step_no, step_type(plan/tool_call/tool_result/answer), content, final_answer
- `eval_run`：run_id, case_id, category, question, expected, got, grader, passed, session_id, ts

## 明确延后（愿景，非今天）

- 真实数据源接入（U8 直连 / MES / Co平台 API）——届时换源适配器即可，上层不动。
- 完整"能否按时交货"跨域长链推理（需**人员排班/产能**等数据，**不在 19 张基础表内**）。
- 19 类之外的写接口、PLM / ERP / OA / 金蝶 等其他源、非结构化/数据湖。
- 宋伟主导的**生产级完整架构**（DuckDB 仅为 PoC 起点）。

## 需要你（用户）配合的事项

1. **钉钉双向(M4)前提**：用自己账户在钉钉开放平台**自建一个内部应用 + 机器人**，把 **AppKey / AppSecret** 给我。（拿不到不影响 M1–M3.5 今天交付，且钉钉 webhook 单向仍可演示。）
2. 确认本机 Python 环境（建议 3.10+）可用。

## 验证（端到端，对应 5 条验收）

1. 跑 `load.py` → 终端打印 19 表行数；打开 Streamlit 仓库视图核对表/行数/预览 → **#1**。
2. CLI 跑 `agent.py` 问演示问题 → 答案正确；管理平台审计/任务链回放出现该会话、每步可见、命中表/行数/SQL 留痕 → **#2**。
3. 跑 `eval/run_eval.py` → 输出通过率与逐条红绿；确定性用例全过、越界用例正确拒答 → **#3**。
4. 钉钉网页向机器人提问 → 收到正确答案；管理平台同步出现该会话 → **#4**。
5. 故意问一个会出错/越界的问题 → 在管理平台按 `session_id` 回放、定位到出错的具体步骤 → **#5**。
