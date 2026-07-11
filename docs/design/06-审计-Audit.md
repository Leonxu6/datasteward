# 06 · 审计（Audit）

> **一句话定位**：审计是平台的"账本层"——把每一次数据访问、鉴权判定、导出和 LLM 推理都写成一条**不可篡改、可分类、可跨服务串联**的日志，回答"谁 / 做了什么 / 何时 / 为何 / 属于哪次操作链"。
>
> **对应我们平台的哪一层**：对应DataSteward 栈的 `dm/connector/` 只读 MCP 连接器写出的 `audit_log.jsonl` + `agent_session.jsonl`，以及 Streamlit 治理台的任务回放。本篇讲的就是如何把这套 JSONL 升级成 Palantir Foundry 的 `audit.3` 规范。

---

## 一、解决什么问题（第一性原理）

审计不是"记日志"这种运维习惯，而是三条硬需求的唯一答案：

1. **可问责（accountability）**——出了事必须能定位到**最下游的真实调用者**（不是中间服务、不是系统账号），并且这条记录本人删不掉、改不掉。没有可问责，一切权限控制都是空中楼阁：权限决定"谁能做什么"，审计证明"谁实际做了什么"。

2. **事后可回溯（forensic traceability）**——一次业务动作（"分析师查了客户表"）在系统内部往往横跨多个服务、多次调用。审计要能把这些散落在不同进程/主机的日志，凭一个共享的 **trace ID** 重新拼回一条完整的动作链，供事后调查逐步还原。

3. **合规（compliance）**——监管与安全审查（SIEM/取证）要求：日志 **append-only**（写入后只增不改，保证审计轨完整性）、**归档隔离**（连管理员都无法悄悄抹掉自己的痕迹）、**低延迟可消费**（安全团队能近实时看到异常，而不是隔天）。

一句话：**权限管"允不允许"，审计管"发生了什么、赖不掉、查得到"。** 二者是同一套治理体系的两面。

---

## 二、Palantir 怎么做（机制）

Palantir Foundry 的审计系统以一套名为 **`audit.3`** 的日志 schema 为核心（前身 `audit.2`）。六个关键机制：

### 1. 统一 envelope + category 并集（union）

- 每条审计日志 = **固定的顶层 envelope 字段**（who/what/when/where/trace）＋ **一组 audit category 的并集**。
- **`audit.3` 强制**每条日志至少带 1 个 category（`audit.2` 里 category 是可选的——这是两版最核心的差异）。
- 一次动作若同时命中多个 category（例如既是"读数据" `dataLoad` 又是"鉴权" `authorizationCheck`），则**一条日志** `categories = [两者]`，并把两者的字段**合并**进同一条记录。这就是官方所说的"日志严格作为多个 audit category 的并集产生"。

### 2. 按业务动作分类（>100 个 category）

- Foundry 官方 category 列表约 **120+ 个**，按**业务动作**而非底层服务名组织：`dataLoad` / `dataExport` / `authorizationCheck` / `managementPermissions` / `llmInference` / `userJustify`……
- 好处：分析者**无需懂底层服务架构**，直接按"我关心导出"或"我关心失败的鉴权"来 filter。

### 3. request / result 分离

- 每个 category 显式声明自己的 **`requestFields`（调用时刻请求了什么，入参）** 与 **`resultFields`（方法执行中派生的信息，即系统实际返回/命中了什么）**。
- 命名迁移：`audit.3` 用 `requestFields`/`resultFields`；`audit.2` 用 `request_params`/`result_params`。
- ⚠️ 官方额外提醒：`audit.2` ↔ `audit.3` **同名字段的内容语义可能不同**，跨版本查询时要两处都查。

### 4. who / what / when / why / trace 五要素落点

| 维度 | 落在哪个字段 |
|---|---|
| **who** | `uid`（用户 ID，明确定义为"**最下游的调用者** most downstream caller"）＋ `orgId`（租户维度） |
| **what** | `categories`（分类）＋ `name`（事件标识）＋ `requestFields`/`resultFields`（细节） |
| **when** | `time`（RFC3339Nano UTC，带纳秒、`Z` 结尾） |
| **why** | 由专门的 **`userJustify`** category 承载，其必填字段 **`userJustification`** 记录"用户执行该动作的理由"——这是"why"的正式载体，直接接 PBAC（基于目的的访问控制） |
| **trace** | `traceId`（Zipkin/B3 分布式追踪 ID，跨服务串联键） |

### 5. trace 跨服务生成与传递

- `traceId` 就是 **Zipkin trace ID**，由 Palantir 开源库 **`palantir/tracing-java`** 实现：
  - client 端往所有请求注入 `X-B3-TraceId: <Trace ID>` HTTP header；
  - Jetty server 端接到后**继续传播**进它后续发起的 client 调用，从而按 Zipkin 规范**跨 JVM/服务边界传播**；
  - 同一次操作横跨的所有服务日志，**共享同一个 traceId**——调查时按 traceId 一拉，完整动作链就还原了。
- Palantir 对标准 Zipkin 的增强：额外发送 **`X-OrigSpanId: <Originating Span ID>`**，使 request log 即便在**未采样（unsampled）**时也能作为 trace 事件的有用子集。
- 实现细节：Span 是**不可变**对象；`CloseableTracer`（单线程）管理 span 生命周期，`DetachedSpan` 支持**跨线程**传播 trace 上下文。
- 另有一套 AIP 可观测性侧的 `foundryTraceId`（Foundry 分配、用于拉遥测）与服务日志 tag 里的 `x-b3-traceid`（best-effort，Ontology SDK 等外部来源可能缺失）。

### 6. append-only 存储 + 隔离归档 + 低延迟交付

- **Append-only**：官方原文——"日志从生成到存储所流经的基础设施被工程化为 append-only，保证审计轨完整性（audit trail integrity）"。（出处：`monitor-audit-logs` 页，非 overview。）
- **隔离归档**：官方原文——"对日志归档存储的访问被极度收紧（aggressively restricted）"。要删除已落地的审计数据须与 Palantir Support 协作制定 remediation 方案就地清除——即**管理员无法悄悄自行删除自己的痕迹**。
- **交付两路**：
  1. **API 轮询**——`list-log-files` + `get-log-file-content` 两个 audit-v2 端点直接拉 `audit.3` 日志（路径 `/api/v2/audit/organizations/{orgId}/logFiles(/{logFileId}/content)`，需 `api:audit-read` scope），**外部 SIEM 无需经 Foundry 中介**即可消费；
  2. **导出**——`audit.2`/`audit.3` 均可由 org admin 配置导出到 per-organization 的 Foundry 数据集。
- **延迟**：`audit.3` 目标 **≤~15 分钟**（最优可到"几分钟"，视使用模式），相对 `audit.2` 的 **24 小时+** 是巨大改进。
- **泄露补救**：`auditDataRedact` category 支持对已落地的审计数据做定向脱敏（data spill remediation）。

---

## 三、Schema / 分类全列表 / 日志示例

### 3.1 顶层 envelope 字段（`audit.3`，逐字段来自官方 overview）

> ⚠️ **对抗验证更正**：本节字段数**不是 12 个**。官方 overview 明确列出的顶层字段**至少 16 个**——`userAgent`、`users`、`entities` 也是**顶层 envelope 字段**（不是"仅导出集才有的列"），且 `users`/`entities` 是官方明确用于聚合的顶层字段。

| 字段 | 语义 | 维度 |
|---|---|---|
| `time` | RFC3339Nano UTC 字符串，例 `2025-11-13T23:20:24.180Z` | when |
| `uid` | 用户 ID（if available），"**最下游的调用者**" | who |
| `orgId` | `uid` 所属组织 | who（租户） |
| `eventId` | 一个可审计**事件**的唯一标识 | — |
| `logEntryId` | **这一行**审计日志的唯一标识 | — |
| `traceId` | "The Zipkin trace ID, if available" | trace |
| `categories` | 本事件产生的所有 audit category（数组） | what |
| `product` | 产生该日志的产品 | — |
| `name` | 事件标识，见下方格式说明 | what |
| `host` | 产生该日志的主机 | where |
| `requestFields` | 调用时刻的入参（请求了什么） | what |
| `resultFields` | 方法执行中派生的信息（实际返回/命中了什么） | what |
| `result` | 成功/失败状态（**含被拒绝的尝试**） | what |
| `userAgent` | 客户端 UA（可查询列，**顶层字段**） | who/where |
| `users` | `set<ContextualizedUser>`，"本条审计日志中出现的所有用户"（**顶层聚合字段**） | who |
| `entities` | list，"请求与结果字段中出现的所有实体"（**顶层聚合字段**） | what |

> **`name` 字段格式（对抗验证硬更正）**：官方原文是 **"generally following a (product name)\_(endpoint name) structure in ALL CAPS, snake-cased"**——即 **SCREAMING_SNAKE_CASE（全大写 + 下划线）**，**不是**普通小写 snake_case。官方示例：`DATA_PROXY_SERVICE_GENERATED_GET_DATASET_AS_CSV2`。
>
> ⚠️ 另：调研初稿把 `resource_id` 列为"导出集列"，但官方文档未证实它是标准列（社区实测的导出 schema 里没有 `resource_id`）——**存疑，不作为可依赖字段**。

### 3.2 审计分类全列表（按业务动作分组；官方 audit-log-categories，约 120+ 个）

**数据操作**
`dataLoad`（用户读取）、`dataExport`（导出/下载出平台，**最高危**）、`dataImport`、`dataCreate`、`dataDelete`、`dataTransform`、`dataMerge`、`dataPromote`、`dataSearch`、`bulkDataImport`

**访问控制 / 鉴权**
`authenticationCheck`（token/认证校验）、`authorizationCheck`（权限校验，**含失败**）、`managementPermissions`（资源权限变更）、`managementGroups`、`managementUsers`、`managementMarkings`（强制标签/mandatory control 变更）

**认证 / 会话**
`userLogin`、`userLogout`、`oauth2InitiateAuthFlow`

**Token**
`tokenGeneration`、`tokenAccess`、`tokenRevoke`、`managementTokens`

**本体 / 逻辑（Ontology）**
`logicCreate` / `logicDelete` / `logicUpdate` / `logicAccess` / `logicSearch`、`ontologyLogic*`、`ontologyDataLoad` / `ontologyDataTransform` / `ontologyDataSearch`、`ontologyMetaData*`

**AI / LLM**
`llmInference`（prompt 执行 + 生成响应）、`llmRoute`（转发到后端）

**代码 / 基建**
`codeExecution`、`cancelCodeExecution`、`configureInfra`、`createInfra`、`containerLaunch` / `containerLoad` / `containerStop`、`restartInfra`、`upgradeInfra`

**元数据**
`metaDataAccess` / `metaDataCreate` / `metaDataDelete` / `metaDataUpdate` / `metaDataSearch`

**监控 / 审批流（接 PBAC）**
`monitorCreate` / `monitorDelete` / `monitorUpdate` / `monitorAccess` / `monitorRun` / `monitorSearch`、`requestCreate` / `requestAccess` / `requestApprove` / `requestDisapprove` / `requestExecute` / `requestCancel` / `requestUpdate` / `requestSearch`

**数据分享**
`dataShare`、`dataShareCreate`、`dataShareDisable`、`auditDataShareCreate`（签名 URL / signed URLs）、`auditDataRedact`（泄露补救时脱敏）

**应用配置 / 资产 / 杂项**
`appConfigAccess` / `appConfigCreate` / `appConfigDelete` / `appConfigUpdate` / `appConfigSearch`、`assetFileLoad`(V2)、`userJustify`（用户目的说明）、`internal`（低信号后端事件兜底 / catch-all）、`passThrough`（参数在运行时决定，通常由外部系统给出）

> ⚠️ **完整枚举说明（见 Open questions #1）**：以上是官方全列表的分组节选，覆盖了实装最常用的 category。官方 `audit-log-categories` 页动态渲染，若要 100% 逐条照抄全部 120+ 个及其字段，需人工用浏览器逐段抓取。**我们栈上只需其中 6–8 个**（见第四节 B）。

### 3.3 各 category 的 request / result 字段（逐字段，官方）

| category | requestFields | resultFields |
|---|---|---|
| `dataLoad` | — | `loadedResources`（**req**，本次加载的 DataResources） |
| `dataExport` | — | `downloadedResources`（**req**）、`downloadedSize`（**req**，字节数） |
| `authorizationCheck` | `authorizationCheckTargets`（opt，被校验的标识）、`authorizationCheckOperations`（**req**，被检查的权限值） | `authorizationCheckSucceededTargets`（**req**）、`authorizationCheckFailedTargets`（**req**）、`authorizationCheckResultMessage`（opt） |
| `userLogin` | — | `loginUserId`（opt） |
| `managementPermissions` | — | `resourcesWithPermissionsChanges`（**req**）、`permissionChangeContext`（opt） |
| `llmInference` | `llmInferenceContext`（**req**）、`llmInferenceInputs`（**req**） | `llmInferenceResponses`（**req**）、`llmInferenceResponseContext`（**req**） |
| `userJustify` | `userJustification`（**req**，"用户执行该动作的理由"） | — |

> ⚠️ **对抗验证要点**：`authorizationCheck` 里 **`authorizationCheckOperations` 是必填（required）**，`authorizationCheckTargets` 是可选（optional）。下面被拒绝场景的 JSON 示例**必须带上 `authorizationCheckOperations`**（初稿漏了）。

### 3.4 一条真实 `audit.3` 日志 JSON schema 示例（照留）

**成功场景**——某分析师读取客户表，被鉴权通过并加载。**一条日志同时命中 `authorizationCheck` + `dataLoad` + `userJustify` 三个 category 的并集**：

```json
{
  "time": "2025-11-13T23:20:24.180Z",
  "uid": "8f3c1e42-....-user-uuid",
  "orgId": "ri.multipass..organization.9a2b-....",
  "eventId": "ri.audit..event.2f1c-....",
  "logEntryId": "ri.audit..logentry.7d4e-....",
  "traceId": "e457b5a2e4d86bd1",
  "host": "foundry-catalog-7c9f-prod",
  "product": "foundry-catalog",
  "name": "CATALOG_GET_DATASET_ROWS",
  "categories": ["authorizationCheck", "dataLoad", "userJustify"],
  "result": "SUCCESS",
  "userAgent": "Mozilla/5.0 ...",
  "requestFields": {
    "authorizationCheckTargets": ["ri.foundry.main.dataset.customers-pii"],
    "authorizationCheckOperations": ["compass:view", "compass:read"],
    "userJustification": "反洗钱调查 AML-2026-Q2-0087：核对交易对手主体"
  },
  "resultFields": {
    "authorizationCheckSucceededTargets": ["ri.foundry.main.dataset.customers-pii"],
    "authorizationCheckFailedTargets": [],
    "authorizationCheckResultMessage": null,
    "loadedResources": ["ri.foundry.main.dataset.customers-pii"]
  }
}
```

**被拒绝场景**——`authorizationCheck` 失败，`result=FAILURE`；与上例**共享同一 `traceId`**（同一次操作链上的另一条日志）：

```json
{
  "time": "2025-11-13T23:20:24.050Z",
  "uid": "8f3c1e42-....-user-uuid",
  "orgId": "ri.multipass..organization.9a2b-....",
  "traceId": "e457b5a2e4d86bd1",
  "categories": ["authorizationCheck"],
  "result": "FAILURE",
  "requestFields": {
    "authorizationCheckTargets": ["ri.foundry.main.dataset.salary"],
    "authorizationCheckOperations": ["compass:view"]
  },
  "resultFields": {
    "authorizationCheckSucceededTargets": [],
    "authorizationCheckFailedTargets": ["ri.foundry.main.dataset.salary"],
    "authorizationCheckResultMessage": "Missing marking: FIN"
  }
}
```

### 3.5 照此实现的关键约束 / 阈值

- Schema 名固定 `audit.3`；每条日志 `categories` **至少 1 个**，为多 category 的并集。
- 顶层 envelope **≥16 个字段**；per-category 字段进 `requestFields`/`resultFields`，required/optional 见 3.3。
- `name` 用 **SCREAMING_SNAKE_CASE**，格式 `(PRODUCT)_(ENDPOINT)`。
- `traceId` 用 **64-bit（16 hex）或 128-bit（32 hex）** 的 Zipkin ID；跨服务用 `X-B3-TraceId` header 透传，Palantir 另加 `X-OrigSpanId`。
- 时间格式必须 **RFC3339Nano UTC**（带纳秒、`Z` 结尾）；**查询/聚合前先按 `time` 过滤**（官方硬性性能要求："Always filter using the time column before performing aggregations or visualizations"）。
- 交付延迟目标 **≤~15min**；API 端点 `list-log-files` + `get-log-file-content`（audit-v2）。
- 存储 **append-only**、归档访问严格受限。

---

## 四、映射到DataSteward 栈（我们怎么复刻）

**目标栈**：StarRocks 数仓 / PostgreSQL 源 / Flink CDC / Neo4j 图 / pgvector / 只读 MCP 连接器 + JSONL 审计 / 无头 Claude 智能体 / Streamlit 治理台。

### A. JSONL 审计升级为 `audit.3` envelope（改 `dm/connector/`）

现状：`audit_log.jsonl` 只记 who/what/when 的松散字段。改成**每行一个 `audit.3` 对象**：

- 固定 envelope：`time`(RFC3339Nano UTC)、`uid`(调用者/服务主体)、`orgId`(先固定单租户 `"dm"`)、`eventId`(uuid4)、`logEntryId`(uuid4)、`traceId`(见 C)、`host`(主机名)、`product`(`"dm-mcp"`/`"dm-agent"`)、`name`(**全大写**，如 `DM_MCP_RUN_SQL`)、`categories`(数组)、`result`(SUCCESS/FAILURE)、`requestFields`、`resultFields`。
- 用 **Pydantic** 定义 `AuditLogEntry` + 每个 category 的 fields 模型，作为 **single source of truth**（呼应本仓 "schema.py 驱动一切"的范式，建议放到 `dm/audit.py`）。

### B. Category 裁剪到我们的动作面（120+ → 约 6–8 个够用）

| 触发点 | category | 字段落点 |
|---|---|---|
| 每次 `run_sql`/查询 | `dataLoad` | `resultFields.loadedResources` = 命中的表/RID 列表 |
| RAG / pgvector 检索 | `dataSearch` | 检索目标 |
| 权限门（见 D，含失败） | `authorizationCheck` | succeeded/failed targets + message |
| session 目的 | `userJustify` | `requestFields.userJustification` |
| 无头 Claude 每步推理 | `llmInference` | `llmInferenceInputs`=脱敏后 prompt 摘要、`llmInferenceResponses`=答案摘要 |
| 治理/变更（未来） | `managementPermissions` / `managementMarkings` | — |
| 结果导出（治理台/钉钉下载） | `dataExport` | `downloadedResources` + `downloadedSize`，**重点监控** |

命名与 required/optional **直接照抄官方字段名**（`loadedResources` / `authorizationCheck*` / `userJustification` 等），保证"Palantir 格式"名副其实。

### C. `trace_id` 跨服务传播（我们的"跨 MCP 调用"链）

- 现有 `session_id` 继续做"**purpose 句柄 / 会话关联键**"，但**另加一个 per-request `trace_id`**：
  - 无头 `claude -p` 每发起一步 → 生成 16 位 hex `trace_id`，经 mcp-config env（如 `DM_TRACE_ID`）注入 MCP 子进程；
  - MCP 若再调 StarRocks/PG/Neo4j/pgvector，把**同一 `trace_id`** 落进各自那条 JSONL。
- 这样"一次用户提问 → 多次工具调用 → 多个后端"的所有日志**共享一个 `trace_id`**，治理台可按 `trace_id` 还原完整动作链（= Palantir 的 `traceId` 语义）。命名对齐 `X-B3-TraceId` 概念，未来接 HTTP 服务时可直接透传。
- **`session_id` 与 `trace_id` 的关系**：`session_id` = purpose（一次会话）；`trace_id` = 一次操作（会话内的一步）。一个 session 下有多个 trace。

### D. `authorizationCheck` 落地（把"只读"升级为可记录的鉴权门）

- MCP 连接器在返回结果前做一次权限判定（哪怕现在只是"表白名单 / 列屏蔽 / 命中 Markings"），**无论放行还是拒绝都写一条 `authorizationCheck`**：成功进 `authorizationCheckSucceededTargets`，失败进 `authorizationCheckFailedTargets` + `authorizationCheckResultMessage`（如 `"Missing marking: PII"`）。
- **被拒绝也必须记**——这是合规审计**第一个会查**的东西（对应权限篇优先级 3）。这也是 `result=FAILURE` 与"含被拒绝的尝试"这一 Palantir 语义的落点。

### E. append-only + 隔离归档（对齐 Palantir 存储保证）

- 现有"JSONL 追加 + DuckDB 只读分离"已是**正确范式**（呼应本仓的 "Storage split" 范式）。
- 上生产：把 `logs/*.jsonl` 定期 append 进 **StarRocks 的一张 append-only 审计表**（或 PG 只追加表），并把归档目录设为**写入进程之外任何人/服务只读**（OS 权限 + 对象存储 WORM / 版本化），复刻"aggressively restricted archival"。
- **切忌**为"方便"允许原地改写日志。

### F. 交付 / 查询（对齐 audit API + Streamlit 治理台）

- Streamlit 治理台现已按 `session_id` 回放任务链——扩展成：
  - 主键改 **`trace_id`**；
  - 支持按 **`categories`** 过滤（尤其 `dataExport` 与失败的 `authorizationCheck`）；
  - **先按 `time` 过滤再聚合**（照 Palantir 性能约束）。
- 这直接把"管理平台是调试工具"升级到"政府级审计视图"。
- 若要"外部 SIEM 直连"语义，可提供一个 read-only HTTP 端点，等价于 `list-log-files` / `get-log-file-content`，返回 newline-delimited JSON（NDJSON）。

### G. eval（呼应本仓约定"新功能需新 eval"）

新增审计 eval 用例：

1. 每次工具调用后断言 JSONL 出现**合法 `audit.3` 行**（schema 校验通过、`categories` 非空）；
2. 一次多步会话内所有日志 **`trace_id` 相同、`session_id` 相同**；
3. 一次被拒绝访问**必产生** `result=FAILURE` 的 `authorizationCheck` 且带 message；
4. `dataExport` **必带** `downloadedSize`。

---

## 五、Open questions

1. **完整 category 全列表（120+）逐条定义**：官方 `audit-log-categories` 页动态渲染，自动抓取只能取到高频子集与其 request/result 字段。若要 100% 照抄全部枚举与每个 category 的字段，需人工用浏览器逐段抓取（或抓其背后的 JSON/API）。**我们栈上只需 6–8 个**，但"声称完全对齐"前应实抓核对。
2. **顶层 envelope 是否还有未列字段**：官方 overview 已确认 ≥16 个字段（含 `userAgent`/`users`/`entities`，以及疑似 `sequenceId`）。是否还有更多、以及导出数据集列是否与顶层字段**完全一致**（还是导出时再摊平），需实测一条真实导出记录确认。`resource_id` 是否为标准列**存疑**。
3. **trace ID 位宽与 span 字段**：确认用 64-bit（16 hex）还是 128-bit（32 hex）Zipkin ID；`audit.3` 顶层只暴露 `traceId`，是否也暴露 `spanId`/`parentSpanId`（B3 三件套）未见文档明列——若我们要**重建 span 树**需自定义。
4. **`result` 的枚举值**：文档只说"成功/失败状态"，未给确切枚举。示例里按 `SUCCESS`/`FAILURE` 写，是否还含 `PARTIAL`/`DENIED` 需实测核对。
5. **audit.2 vs audit.3 双写**：官方仍在两 schema 间迁移（`traceId` 可跨 `audit.2`/`audit.3` 关联；同名字段内容可能不同）。我们直接**单一 `audit.3`** 即可，但要留意某些 category 是否仅存在于其中一个 schema。
6. **隔离归档的强度门槛**：官方只定性说"aggressively restricted / append-only"，未给具体控制项（WORM？保留期？密钥托管？）。这些属 FedRAMP/IL6 合规工程细节，应按**自身场景（非政府合规）的实际要求**决策到什么强度，而非照搬政府级。
7. **`llmInference` 输入/输出脱敏策略**：Palantir 记 `llmInferenceInputs`/`llmInferenceResponses`，但制造客户的 prompt 可能含业务敏感数据。落地时是记全文、还是摘要/哈希，是一个需与用户决策的**隐私 / 审计权衡点**。

---

## 六、来源

**Palantir 官方文档**
- Audit logs overview — https://www.palantir.com/docs/foundry/security/audit-logs-overview
- Audit log categories（全列表）— https://www.palantir.com/docs/foundry/security/audit-log-categories
- Monitor audit logs（append-only / 归档受限 / time 过滤原文出处）— https://www.palantir.com/docs/foundry/security/monitor-audit-logs
- Audit v2 API — log file basics — https://www.palantir.com/docs/foundry/api/audit-v2-resources/log-files/log-file-basics
- Audit v2 API — list-log-files — https://www.palantir.com/docs/foundry/api/audit-v2-resources/log-files/list-log-files
- AIP observability — trace view（foundryTraceId / x-b3-traceid）— https://www.palantir.com/docs/foundry/aip-observability/trace-view
- Configure logging — https://www.palantir.com/docs/foundry/administration/configure-logging

**Palantir 开源 / 博客**
- `palantir/tracing-java`（X-B3-TraceId / X-OrigSpanId / CloseableTracer / DetachedSpan）— https://github.com/palantir/tracing-java
- OpenZipkin B3 propagation 规范 — https://github.com/openzipkin/b3-propagation
- Building trust at scale（schema / 交付 / SIEM，"几分钟"延迟措辞出处）— https://blog.palantir.com/building-trust-at-scale-33f6e2f5f8f9

**社区实测（导出 schema 参照）**
- How to query audit logs v3 via API — https://community.palantir.com/t/how-to-query-audit-logs-v3-via-api-in-a-lightweight-transform/6093
