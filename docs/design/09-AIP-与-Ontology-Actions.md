# 09 · AIP 与 Ontology Actions

> **一句话定位**：AIP 是把整条数据平台"从回答问题推进到安全地采取行动"的**行动闭环层**——用户用自然语言提出意图，系统在 Ontology 语义层上**检索 → 用工具读算 → 决策 → 经受治理的 Action 写回 → 全程留痕**，读半边靠只读查询、写半边靠一道"validate/apply 窄门"。
>
> **我们与 Palantir 唯一有意的差异**：Palantir 的 AIP 底座偏**工作流（AIP Logic 是无状态 LLM 函数、Agent Studio 是编排好的对话体）**；**我们用一个无头智能体（`claude -p` + MCP）实现 AIP**——同样的"检索/工具/治理写回/审计"能力，但编排交给智能体自主的多步推理，而不是预先画好的逻辑块。本文最后一节把这个取舍讲透。
>
> **与 `SPEC.md` 的分工**：本文讲"为什么这样设计 + 端到端怎么跑通"（第一性原理 + 执行形态），字段名/枚举/JSON schema/REST 接口等**实装规格**已在 `SPEC.md` §2.9（AIP-Action）与 §3.3–§3.5（我们栈映射）挖到位，本文只在必要处引用、不重复照抄。

---

## 一、解决什么问题（第一性原理）

前八篇文档把平台建成了一台"**能被可靠地问问题**"的机器：连接器把源数据搬进来（01），转换把它清洗成规范数据集（02），Ontology 把数据集升成有语义的对象/链接（03），权限/审计/血缘/健康横切保证每一次读都合规可溯（04–07），报表与 Control Panel 让人和 AI 都能看/筛/探（08）。

但"能回答问题"只是价值的一半。真实业务里，**问完之后总要动手**：

- "SO0001 够不够发货？" —— 回答完，接着就是"**那就发货**"：扣减库存、生成发货单、通知仓库。
- "M0046 快断料了" —— 回答完，接着是"**建一张采购订单**"：选供应商、下 PO、走审批。
- "这批工单进度落后" —— 回答完，接着是"**改排产**"或"**升级告警**"。

**从"回答问题"到"安全地采取行动"，中间横着四道坎**，也正是 AIP 要解决的核心问题：

1. **副作用不可逆**：读错了顶多是信息误导，写错了是真金白银的库存被扣、真实的 PO 被下。裸 `UPDATE` / `INSERT` 让 LLM 直连数据库是灾难——模型会幻觉、会算错、会被 prompt 注入。**写必须有护栏**。

2. **权限必须一致**：一个能"看"某数据的用户，未必有权"改"它；反过来，能改的未必看得全（比如客服能改工单状态却看不到全部客户 PII）。**AI 采取行动时，有效权限必须 ≤ 调用它的人**——绝不能因为"经过了 AI"就绕过治理。Palantir 的总纲原话：*"all governance and security controls apply equally to AI agents and humans"*。

3. **决策要有依据、可复现**：LLM 是非确定性的。同一个"够不够发货"，它不能靠训练记忆瞎猜，必须**基于当前认证过的对象数据**来算；而且这条"检索→决策→动作"链要能**回放**（出错了要能定位是哪一步错），要能**离线回归测试**（改了 prompt/工具后不能偷偷变坏）。

4. **抑制幻觉的边界**：LLM 的知识边界必须被物理收窄到"完成任务所需的最小认证数据集"。Palantir 的做法是 *"restricting LLM access exclusively to authenticated Ontology data rather than relying on model training data"*——只喂本体数据、不信训练记忆，权限经 Ontology permissions + function-level security 收到最小集。

**AIP 的答案**：把"采取行动"这件事，焊死在 Ontology 语义层上。读走**只读查询工具**（Object Query / 检索注入），写走**唯一一道 validate/apply 窄门**（governed Action），全程**权限即审计**，事后**离线 evals 回归**。人和 AI 走同一套护栏，AI 只是"多了一个非人类的调用者"。

---

## 二、Palantir 怎么做（机制）

Palantir 的 AIP 由**三大构建工具 + 一个内置 copilot**组成，全部长在 Ontology 上。字段级规格见 `SPEC.md §2.9`，这里讲机制骨架与"为什么"。

### 2.1 三条构建线 + copilot

| 构件 | 形态 | 一句话本质 |
|---|---|---|
| **AIP Logic** | 无状态"LLM 函数" | 一个 **Use LLM block**（Prompt + Tools + 结构化 Output），带类型签名、可被 Workshop/Agent/API/另一个 Logic 调用的生产函数。**这是 Palantir "工作流式 AIP" 的核心单元**。 |
| **Agent Studio**（现名 Chatbot Studio） | 有状态对话体 | 比 Logic 多：多轮 application state 进 prompt、三种 retrieval context、6+ 类工具、可内外部部署（平台内 + Ontology SDK/API 对外）。 |
| **AIP Evals** | 离线回归框架 | *"对非确定性 LLM 输出做确定性测试"*。可评 Logic / Agent / 代码函数；graders 分确定性 / LLM-backed / 自定义；**官方建议每用例跑 ≥3 次再聚合**。 |
| **AIP Assist** | 平台内置 copilot | Cmd/Ctrl+Shift+U 唤起，可挂自建 chatbot + 自定义 Markdown 内容源。 |

> **关键观察**：Palantir 把"AI 逻辑"当**函数**来治理——AIP Logic 是无状态、有类型签名、可组合、可被 Evals 覆盖的生产工件。这是典型的**工作流思路**：先把每条 AI 能力固化成可复用的块，再由更外层（Workshop 按钮、Agent 编排、另一个 Logic）串起来。这与我们"让智能体自主多步推理"的路线正好形成对照（见第四节）。

### 2.2 Ontology-aware 检索注入（每条消息确定性执行）

Agent Studio 的每条用户消息，都会**先确定性地跑一遍检索**，把结果拼进 system prompt，再交给 LLM。三种 retrieval context：

- **Ontology context**（检索结构化对象图）：对象集来源 = Static input（整个对象类型）或 Variable input（经 application state 过滤）；检索模式 = 固定 N 个对象 或 **语义检索 top-K**（需对象类型上有 vector embedding 属性）；可勾选哪些属性进 prompt（默认全选可打印属性，排除 media reference / vector embedding 以省 token）；产出 object set 变量 + citation 变量。
- **Document context**（非结构化文档）：整篇全文 或 **语义检索 top-K chunks**（chunks 模式 beta，需申请开通）。
- **Function-backed context**（自定义检索逻辑）：TypeScript 注解 `@AipAgentsContextRetrieval()`，唯一必填入参 `messages: MessageList`，返回 `retrievedPrompt: string`——官方原话 *"pasted into the LLM system prompt"*。

**为什么是"确定性检索 + 拼进 prompt"而不是让模型自己去查？** 因为这一步是**信息注入的可控闸门**：由平台决定"这条消息该带哪些对象/文档进上下文"，既抑制幻觉（模型只看喂进来的认证数据），又省 token（只注入白名单属性），还产出 citation 便于溯源。

### 2.3 prompted vs native tool calling

LLM 拿到检索注入后的 prompt，要决定**调哪个工具**。有两种工具调用机制：

| | Prompted tool calling | Native tool calling |
|---|---|---|
| 机制 | 工具说明写进 prompt，模型输出"我要调 X"，平台解析后执行 | 用模型**原生 function-calling** 能力 |
| 并发 | 一次调一个、**顺序执行** | 可**并行多工具** |
| token | 较费（工具说明占 prompt） | 更省 |
| 兼容性 | **全部模型 + 全部工具类型** | 仅**一部分 Palantir 自家模型** + **4 类工具**（Actions / Object Query / Function / Update Application Variable） |
| 退化 | —— | 不支持的模型/工具类型**自动退回 prompted** |

部署后的 chatbot 提供 **View reasoning**（在 edit / view / Workshop / AIP Threads 均可查看），展示 LLM 的决策链——这就是"可回放"落地。

**6+ 类 agent 工具**：`Action`（自动执行 或 需用户确认）、`Object Query`（过滤 / 聚合 / inspection / 沿 link 遍历）、`Function`（调 Foundry 函数，含已发布的 AIP Logic，自动选最新版或手动指定版本）、`Update Application Variable`、`Command`（触发其他 Palantir 应用）、`Request Clarification`（暂停反问用户补参数）。

> **注意四类工具的分工正好对应"读 / 算 / 写"**：Object Query = 读对象图，Function = 算业务逻辑，Action = 写回（唯一动手的），Request Clarification = 缺参时不硬来、反问。这是安全 agent 的典型工具集设计。

### 2.4 通过 governed Action 安全写回（AI 动手的唯一窄门）

**这是整个 AIP 治理的核心**：LLM 无论多聪明，**想改任何东西，只能经过 Action Type**——绝不暴露裸 UPDATE。Action Type = 带三环护栏的"业务动词"（完整规格见 `SPEC.md §2.3` Action Type 与 §2.9）：

- **(a) Rules（副作用编排）**：声明"这个动作到底改什么"。11 类 ontology 规则——Create / Modify / Create-or-modify / Delete object(s)、Create / Delete link(s)、**Function rule**（引用 Ontology edit 函数，且"**存在时不可配其他 rule**"）、外加 4 类 interface 变体。属性赋值四法：`From parameter` / `Object parameter property` / `Static value` / `Current User·Time`。**非法组合被硬禁**：删在增/改前、改在增前、同次创建两次。另有 Notification rule / Webhook rule（可选 edits 前/后执行，用于回写外部 ERP/MES）/ Schedule rule。

- **(b) Submission criteria（提交条件，原 validations）**：编码"**谁能在什么参数下提交**"。由 conditions + operators 组成，支持按 user ID / group IDs（含继承成员）/ Multipass 属性 / 参数值比较；**不支持** attachment 与 object set 参数；**所有条件全过才能提交**，且与"能否编辑该 action type 本身"相互独立。

- **(c) Permissions（权限绑定）**：提交一个 action 需**同时满足**三件事——① 能 view 被编辑的对象类型/link 类型及其 datasource；② 通过 submission criteria；③ 满足 writeback 设置的编辑权（两档：**actions-only 对象**只需被编对象的 **Read**，官方推荐，实现"用户能编辑其可见但不能独立查看的记录"；**multi-edit 对象**需对所有被编对象的 writeback dataset 持 **Edit**，官方 discouraged）。三个权限维度：谁能 **view** / **edit** / **apply**（带特定参数）该 action type。**副作用只在 submission criteria 全过后才触发**。

**权限绑定的总纲**（本文反复强调，因为它是"让 AI 安全动手"的地基）：

> *"all governance and security controls apply equally to AI agents and humans"* —— **AI agent 与人走同一套权限，agent 的有效权限 ≤ 调用者。**

### 2.5 写前 Validate 与写入 Apply（两个 REST 端点）

Action 通过两个 REST 端点暴露（完整 schema 见 `SPEC.md §2.9`）：

- **Validate**（写前校验，**agent 决策的关键**）：`POST .../actions/{actionType}/validate`（scope `api:ontologies-read`）。返回 `{ result: VALID|INVALID, submissionCriteria: [...], parameters: { <pid>: { result, required, evaluatedConstraints: [...] } } }`。
  - **一条极其重要的边界**：官方明确 *"Validations will not consider existing objects or other data in Foundry"*——**validate 不查现有对象**。也就是说"库存到底够不够发货"这种**依赖当前数据的业务真值，validate 管不了，必须靠 Object Query 侧独立算**。这直接决定了 agent 的决策逻辑：不能只靠 validate 就下结论。

- **Apply**（真正写入）：`POST .../actions/{actionType}/apply`（scope `api:ontologies-read api:ontologies-write`），body `{"parameters": { ... }}`。**边改边校验 + 权限 + 审计**，落 Ontology 并留 lineage。options 有 `returnEdits` / `validateOnly`（二者互斥）；不支持参数默认值（未传即 null）。

### 2.6 evals 跑多次聚合

AIP Evals 用**确定性测试框架去覆盖非确定性输出**。graders 三类（确定性 / LLM-backed / 自定义，全表见 `SPEC.md §2.9`）。核心方法论有两条：

- **多次运行再聚合**：*"running test cases at least three times for LLM-backed functions is recommended"*——因为单次跑绿可能是运气，**多次聚合才能压住非确定性误判**。
- **objectives/阈值**：bool 指标指定应为 true/false；maximize 指标设最小阈（≥X）；minimize 指标设最大阈（≤X）；单指标达标即 pass，一次迭代内**全指标达标该迭代才 pass**；结果表支持 Group by 看分组通过率。

---

## 三、端到端执行形态

把上面拆开的机制拼成一条完整的 agent 执行链——**检索 → 工具（读/算）→ 决策 → Action（validate → apply）→ 回写 → 循环 → 回放 → 回归**。硬细节（端点、枚举、约束）照留：

```
① 用户自然语言意图（例："SO0001 库存够就直接发货"）
        │
        ▼
② 【确定性检索注入】每条消息触发 retrieval → 拼进 system prompt
   · Ontology context：按对象类型取 N 个 或 pgvector 语义 top-K（仅注入白名单属性省 token）→ 产出 object set + citation
   · Document context：整篇全文 或 语义 top-K chunks
   · Function-backed context：@AipAgentsContextRetrieval(messages) → retrievedPrompt 贴进 prompt
        │
        ▼
③ 【工具选择】LLM 经 prompted / native tool calling 选工具
   （native：并行、省 token，仅 Palantir 部分模型 + 4 类工具；否则退回 prompted 顺序调）
        │
        ▼
④ 【读 + 算】
   · Object Query 读对象图：沿 link 遍历、过滤、聚合 →「SO0001 需求 265，M0046 现有库存 X」
   · Function 算业务逻辑：可发量、缺料判断
        │
        ▼
⑤ 【LLM 决策】库存 ≥ 需求？
   · 缺参数 → Request Clarification 暂停反问用户（不硬来）
   · 需要写 → 进入 Action 窄门（⑥）
   · 不满足 → 带解释终止 / 转"建 PO"另一条链
        │
        ▼
⑥ 【写前 Validate】POST .../actions/shipOrder/validate
   返回 result: VALID|INVALID + submissionCriteria[]{configuredFailureMessage,result} + 每参数 evaluatedConstraints
   · INVALID → 带 configuredFailureMessage 反问用户 / 终止（绝不 apply）
   · ⚠ validate 不查现有对象 → "库存够不够"的真值已在 ④ 用 Object Query 算过，validate 只管"参数/权限/提交条件"
        │ VALID
        ▼
⑦ 【写入 Apply】POST .../actions/shipOrder/apply  body {"parameters":{...}}
   · 边改边校验 + 权限（agent 有效权限 ≤ 调用者）+ 审计
   · Rules 执行副作用：Modify object(库存-265) + Create link(order→shipment)
   · 落 Ontology + 留 lineage；Side effect（Webhook 回写 ERP/MES / Notification 通知仓库）
        │
        ▼
⑧ 【循环】apply 结果喂回 LLM → 继续推理直到给出终答（"已发货，剩余库存 X"）
        │
        ▼
⑨ 【回放】View reasoning 展示完整决策链（选了哪些工具、validate 结果、apply 参数）
        │
        ▼
⑩ 【回归】AIP Evals 离线对整条 Logic/agent 跑测试套件（每用例 ≥3 次聚合），防止改动偷偷变坏
```

**这条链的三个"安全支点"**（务必记牢）：

1. **④ 与 ⑥ 的分工**：业务真值（库存够不够）在 ④ 用 Object Query **实算**；⑥ 的 validate 只校验参数/提交条件/权限，**不碰现有数据**。把这两件事混淆，就会写出"validate 通过了以为库存够"的致命 bug。
2. **⑥ → ⑦ 的窄门**：任何写入前**必须先 validate，INVALID 绝不 apply**——validate 是"能不能提交"的守门人。
3. **⑦ 的权限即审计**：apply 边改边校验权限、边落 lineage，**agent 权限 ≤ 调用者**，且全程留痕，事后可经 ⑨ 回放、⑩ 回归。

---

## 四、映射到DataSteward 栈（我们怎么复刻）

> 我们的栈：StarRocks（OLAP 数仓）/ PostgreSQL（OLTP 源）/ Flink CDC（增量同步）/ Neo4j（图/血缘）/ pgvector（语义检索）/ **只读 MCP 连接器 + JSONL 审计** / **无头 Claude（`claude -p`）** / Streamlit 治理台。
>
> **总纲**：我们已经复刻了 AIP 的"**只读半边**"（Object Query 类工具 = 现有 3 个只读 MCP 工具）。要对齐 AIP，最大缺口是"**governed Action 写回层**"。逐子系统的字段级映射见 `SPEC.md §3.3–§3.5`，本节讲"我们用 agent 实现 AIP"的架构与取舍。

### 4.1 无头 Claude 智能体 = 我们的 AIP

**这是我们与 Palantir 唯一有意的差异**：

| 维度 | Palantir AIP（工作流式） | 我们（智能体式） |
|---|---|---|
| AI 逻辑单元 | **AIP Logic**：无状态、有类型签名的 LLM 函数，预先固化每条能力 | **无头 Claude `claude -p`**：一个自主多步推理的智能体，编排交给模型 |
| 编排 | Agent Studio / Workshop 按钮**预先编排**逻辑块的调用 | 智能体**运行时自主决定**调哪个工具、调几次、什么顺序 |
| 工具调用 | prompted / native tool calling（native 限自家模型 + 4 类工具） | **Anthropic 原生 tool use ≈ native tool calling**（可并行、省 token），默认走原生；后备模型退回 prompted |
| 检索注入 | 三种 retrieval context 确定性拼 prompt | 同款三通道，落在 MCP：Ontology context（Neo4j/StarRocks 按对象类型取 N 个 或 pgvector 语义 top-K，仅注入白名单属性）、Document context（pgvector top-K chunks）、Function-backed context（一个 Python 函数返回 `retrievedPrompt`，等价 `@AipAgentsContextRetrieval`） |
| 回放 | View reasoning | `audit_log.jsonl` + `agent_session.jsonl` 按 `session_id` 关联的任务链回放（Streamlit 治理台，见 `dm/app/app.py`） |

**为什么选智能体而非工作流？** 我们要的是"用户抛一句自然语言，系统自己想清楚要读什么、算什么、要不要写、写什么"的**端到端自主性**——这正是智能体的强项。工作流式 AIP 的优势是每条链路可控、可复用、易治理；智能体的优势是灵活、能处理未预设的组合意图。取舍点在**第 4.4 节**。

### 4.2 新增 execute_action 治理化写回工具（最大缺口）

**当前栈全只读，写回层是第一优先级缺口。** 复刻方式：**新建一个"只读 MCP 之外"的受治理写 MCP/服务**，把每个业务操作封装成 Action Type（如 `shipOrder` / `createPurchaseOrder`），**绝不暴露裸 UPDATE**。三环护栏落地（详见 `SPEC.md §3.3` 的 Action 行、`§3.4` 的写回执行门）：

- **(a) Rules**：用一张 action 定义注册表（YAML/JSON SSOT）声明 create/modify/delete/link 规则 + 属性赋值来源（from parameter / object property / static / current user·time）。执行时生成对 **PostgreSQL 源库**的写（OLTP 事务强），再经 **Flink CDC 同步回 StarRocks** 形成闭环。
- **(b) Submission criteria**：实现一个 `validate` 端点，**照抄 Palantir 响应 schema**（`{result, submissionCriteria:[{configuredFailureMessage,result}], parameters:{<pid>:{result,required,evaluatedConstraints:[{type:range|oneOf|arraySize|...}]}}}`）。conditions + operators 编码"数量 > 0、不超授信、user 在某 group"等业务规则。**agent 决策前必须先调 validate**。
- **(c) Permissions（权限即审计）**：写前校验"调用用户能 view 被编对象 + 通过 submission criteria + 对 writeback 表有 Edit"；**agent 有效权限 = 调用者权限**，不给 agent 超级权限。

**HTTP 形态直接仿 Palantir**：`POST /actions/{actionType}/validate` 与 `/apply`，body `{"parameters":{...}}`。apply 成功后写 JSONL 审计（who / session_id / actionType / parameters / edits / 结果），把现有"事后日志"升级成"**权限即留痕 + edits lineage**"。

**审批 + 回滚**（对齐 Palantir 的 Action + Approvals + 事务语义，也是我们要显式落地的治理面）：
- **审批**：Action 定义里声明"是否需人工确认"（对齐 Palantir agent 工具的"自动执行 vs 需用户确认"、以及 PBAC 的 Approvals 应用）——高风险动作（下 PO、大额扣减）走钉钉审批卡再 apply。
- **回滚**：apply 落 PostgreSQL 源库时以**数据库事务为边界**，失败整体回滚不留半截；复杂多对象写回走一个"Ontology edit 函数"式的事务函数（对齐 Function rule "存在时不可配其他 rule"，把一次多对象编辑收进单事务）。

### 4.3 与只读工具组合成 agent 工具集

无头 Claude 的工具集 = **只读查询工具（现有）+ 受治理写工具（新增）+ Function + Request Clarification**，正好对齐 Palantir 的四类 agent 工具（读 / 算 / 写 / 反问）：

| Palantir agent 工具 | 我们的工具 | 状态 |
|---|---|---|
| Object Query（读对象图） | `run_sql`（StarRocks 只读）+ `graph_query`（Neo4j 沿关系遍历/聚合） | **已有** |
| （检索注入 / 文档） | `search_documents`（pgvector 语义 top-K chunks） | **已有** |
| Action（写回） | **`execute_action`**（validate + apply 窄门，见 4.2） | **新增，最大缺口** |
| Function（算业务逻辑） | 把高频业务 SQL/Python（可发量、缺料判断）固化成"强类型函数" | 新增 |
| Request Clarification | 缺参时反问（agent 提示词/工具约定层面） | 新增 |

**一条完整链路示例**（对齐第三节的端到端形态）：用户问"SO0001 够就发货" → Claude 经 `graph_query`/`run_sql` 读对象图算出库存 vs 需求（对应 ④）→ 决策（⑤）→ 调 `execute_action` 的 validate（INVALID 就带 `configuredFailureMessage` 反问/终止，对应 ⑥）→ VALID 才 apply（对应 ⑦，写 PostgreSQL → CDC 回 StarRocks）→ 审计留痕 → Streamlit 按 `session_id` 回放（对应 ⑨）。

**Evals 对齐**（对应 ⑩）：现有 `dm-eval`（SQL 真值 + LLM-judge + 拒绝测试）已高度同构 AIP Evals。补两条即对齐：**每用例跑 ≥3 次再聚合**（降非确定性误判）+ 加 **Rubric grader / Contains key details**（按量规打分、校验关键事实齐全），并给数值指标设 maximize 最小阈 / minimize 最大阈、结果 Group by 看分组通过率。**新增写回 Action 后必须补新 eval 用例**（本仓约定：新功能 = 新 eval）。

### 4.4 与 Palantir 工作流式 AIP 的差异与取舍

| 维度 | 工作流式（Palantir） | 智能体式（我们） | 取舍 |
|---|---|---|---|
| **灵活性** | 逻辑块预先固化，组合受限于编排 | 智能体运行时自主组合工具，能处理未预设意图 | 我们赢在灵活，适合 PoC 探索期"一句话到行动" |
| **可控/可复现** | 每条 Logic 有类型签名、可被 Evals 精确覆盖 | 多步推理路径非确定，回放靠 session 关联日志 | Palantir 赢在可控；我们靠"validate 窄门 + 审计 + eval ≥3 次"补齐 |
| **治理面** | 治理点清晰（每个 Logic/Action 独立授权） | 治理全压在 `execute_action` 窄门这一层 | 我们把治理**收敛到单一写入口**，反而更易审计——只要守住这道门 |
| **性能/token** | native tool calling 限自家模型 | Anthropic 原生 tool use（并行、省 token） | 各有底座依赖 |
| **抑幻觉** | LLM 只access 认证 Ontology 数据 | 同理：只读 MCP + 检索注入把数据边界收窄 | 一致 |

**共同的不可让渡红线**（无论工作流还是智能体，都不动摇）：
1. **写必过 validate/apply 窄门**，绝不裸 UPDATE。
2. **agent 有效权限 ≤ 调用者**，AI 与人同一套护栏。
3. **全程审计 + 可回放 + 离线 eval 回归**。

**一句话总结取舍**：Palantir 用"把 AI 能力固化成受治理的工作流块"求可控；我们用"把治理收敛到单一写入口 + 智能体自主编排"求灵活——**两条路守的是同一套安全红线，只是把复杂度放在了不同的地方**（Palantir 放在编排层，我们放在写入口 + eval）。

---

## 五、Open questions

以下问题官方文档未完全公开，或我们复刻时需自定并实测（承接 `f_aip.md` 调研，落到我们栈的决策项）：

1. **原生 tool use 与 native tool calling 是否语义等价**：Palantir 只说 native 支持"a subset of Palantir-provided models"，未给清单。我们用 Anthropic 原生 tool use 的"并行多工具"是否与其完全等价，需实测——**尤其并发写 Action 的顺序/冲突处理**（多个 Action 并行 apply 时的隔离性）。

2. **evals 多次运行的"聚合"口径**：官方建议"≥3 次"但未给聚合公式（多数投票？平均分？阈值判 pass 的口径）。我们自建 `dm-eval` 聚合时需**自定义口径并记录**，避免"单次绿 = 假绿"。

3. **Apply 的原子性/回滚语义**：文档只给了"非法编辑顺序"约束，未明确一次 apply 内多对象编辑失败是否**整体回滚**，也未明说 v1/v2 的 batch/transaction 差异。我们写回层需**实测 PostgreSQL 事务边界**，把"一次 Action = 一个数据库事务"定死。

4. **库存校验放哪**：validate 明确"不查现有对象"，所以"够不够发货"必须由 Object Query 侧独立算。决策项：把库存校验放进 submission criteria（用 `objectQueryResult` 约束类型？官方对其能力边界未细说）还是放在 **agent 决策逻辑**里。我们倾向后者（agent 先 `run_sql`/`graph_query` 算真值，validate 只管参数/权限）。

5. **复杂多对象写回的默认形态**：Function rule "存在时不可配其他 rule" 意味着复杂写回可能必须全走一个 Ontology edit 函数。我们需定写回层默认形态——建议**多对象写回一律走一个事务函数**（对齐此约束，也天然拿到原子性）。

6. **Function-backed retrieval 的上限与调参**：`retrievedPrompt` 有无长度/token 上限、语义检索 chunk 的默认 K 值与切分策略，官方未给数字。我们 **pgvector 侧需自定并 eval 调参**。

7. **身份链如何贯通**："agent = 调用者交集"在无头 Claude + MCP 架构下**如何传递调用者身份**——现在靠 `session_id` 注入 `DM_DATA_DIR`。需设计一套"调用用户 → 有效权限 → 写回校验"贯通的身份链；官方 role/marking/purpose 三控的落地粒度需我们**自定映射**（见 `SPEC.md §3.4` 的策略元表设计）。

---

## 六、来源

调研原料：`scratchpad/research/f_aip.md`（对抗验证过的实装级调研）。原始官方文档：

- AIP 总览 / 架构：
  - https://www.palantir.com/docs/foundry/aip/overview
  - https://www.palantir.com/docs/foundry/architecture-center/aip-architecture
- AIP Logic：
  - https://www.palantir.com/docs/foundry/logic/overview
  - https://www.palantir.com/docs/foundry/logic/getting-started
- Agent Studio / Chatbot Studio（工具 + 检索 + 核心概念）：
  - https://www.palantir.com/docs/foundry/agent-studio/tools
  - https://www.palantir.com/docs/foundry/chatbot-studio/tools
  - https://www.palantir.com/docs/foundry/agent-studio/retrieval-context
  - https://www.palantir.com/docs/foundry/agent-studio/core-concepts
- AIP Evals：
  - https://www.palantir.com/docs/foundry/aip-evals/overview
  - https://www.palantir.com/docs/foundry/aip-evals/create-suite
  - https://www.palantir.com/docs/foundry/aip-evals/run-suite
  - https://www.palantir.com/docs/foundry/aip-evals/analyze-run-results
- Action Types（governed 写回三环护栏）：
  - https://www.palantir.com/docs/foundry/action-types/overview
  - https://www.palantir.com/docs/foundry/action-types/rules
  - https://www.palantir.com/docs/foundry/action-types/submission-criteria
  - https://www.palantir.com/docs/foundry/action-types/permissions
  - https://www.palantir.com/docs/foundry/action-types/parameter-overview
- REST API（validate / apply）：
  - https://www.palantir.com/docs/foundry/api/ontology-resources/actions/apply-action
  - https://www.palantir.com/docs/foundry/api/ontology-resources/actions/validate-action
- OSDK / BYOM / Assist：
  - https://www.palantir.com/docs/foundry/ontology-sdk/python-osdk
  - https://www.palantir.com/docs/foundry/ontology-sdk/typescript-osdk
  - https://www.palantir.com/docs/foundry/aip/bring-your-own-model
  - https://www.palantir.com/docs/foundry/assist/overview

> **相邻文档**：Ontology 名词/动词五构件见 03；权限（Markings/Roles/写回门）见 04；审计 audit.3 见 05；本文与 `SPEC.md §2.9 / §3.3–§3.5` 互为"叙述 ↔ 实装规格"。
