# 08 · 应用层 Workshop 与管理者视图

> Palantir Foundry 的"应用层"是把本体（Ontology）里的数据变成一线员工能直接操作的界面：Workshop 拼装操作型应用、Object Explorer 做即席探索、Control Panel 供管理者管人/管资源/看审计。对应我们平台的**最上层——Streamlit 治理台的用户可见页面**（对象工作台、报表、探索页、管理者页），即"报表显示什么、管理者能看到什么"这一层。

---

## 一、解决什么问题（第一性原理）

前七篇讲的是数据怎么进来、怎么建模、怎么被智能体读取。但数据平台的价值最终要落在**一线的人在屏幕上看到什么、能点什么**。这一层要回答两个第一性问题：

**1. 操作型应用（Operational App） vs 纯仪表盘（Dashboard）——本质区别是"能不能改变现实"。**

- **纯仪表盘**：单向只读。用户只能"看、筛、导"（看数字、按条件过滤、导出 CSV/Excel）。它告诉你"发生了什么"，但改变不了任何东西。
- **操作型应用**：看 + **通过 Action 触发 writeback 改变现实**（审批一张单、给某台机床派工、把决策回写 ERP）。它把用户放在一条 **on-rails（轨道式）工作流**上——不是给你一片自由画布，而是把"下一步该做什么"限定成几个受控动作，并常常捕获用户输入（行内编辑、表单、内联 Action）。

这个分界是整篇的钥匙：**报表 = 看数字；操作应用 = 看数字 + 按钮点下去真的改了库**。Palantir 的三条铁律贯穿始终——**读走对象（Object）、写走 Action、每步留痕（Audit）**。

**2. 管理者视图——谁在用、用了多少、动过什么，要有一处集中看。**

平台一旦有多人使用，管理者就需要回答：哪些用户/角色能看哪些资源？算力和存储花了多少、超没超预算？谁在什么时间对哪个对象做了什么操作、成功还是被拒？这三类问题（用户/角色、资源/健康、活动/审计）在 Foundry 里统一收进 **Control Panel**。对我们，它对应治理台里专门给"管理者"的页面——不是花哨的展示，而是**排障与治理的工具**。

---

## 二、Palantir 怎么做（机制）

### 2.1 Workshop 操作应用：用 widget 拼装、用变量联动

Workshop 是 Foundry 的应用搭建工具，用**拖拽 widget（部件）**的方式组装应用，不写 React 也能有交互。官方把 widget 分为 **4 大类**，另有 **3 个补充类**（AIP / 嵌入 Foundry 应用 / 移动端专用）：

| 类别 | 代表 widget |
| --- | --- |
| **① 展示型 Core display** | Object Table、Object List、Object View、Property List、Links、Object Set Title |
| **② 可视化型 Visualization** | Chart XY、Vega Chart、Map、Gantt Chart、Pie Chart、Stepper、Markdown、Metric Card、Pivot Table、Timeline、Resource List、Media Preview、Spreadsheet Display、PDF Viewer、Image Annotation、Free-form Analysis、Time Series Analysis、Data Freshness、Edit History、Linked Compass Resources、Action Log Timeline |
| **③ 筛选型 Filtering** | Filter List、Object Dropdown、Object Selector（多选对象）、String Selector、Date and Time Picker、Text Input、Numeric Input、Exploration Filter Pills、Exploration Search Bar、Prominent Term、User Select |
| **④ 事件/导航型 Event-triggering & navigational** | Button Group、Media Uploader、Comments、Tabs、Inline Action、Audio Recorder |
| **补充：AIP** | AIP Analyst / AIP Chatbot / AIP Generated Content |

**联动机制（响应式、事件驱动）**：每个 widget 有 **input variables**（传入的数据，如一个 object set）和 **output variables**（传出给下游 widget 的数据）。变量类型包括 object set、object set filter、string/number、date 等。**某个 widget 改了一个变量 → 所有依赖该变量的 widget 自动重渲染**。这就是"不写 React 也有交互"的原理：筛选器改了 filter 变量，表格和 KPI 卡片就一起刷新。

### 2.2 Object Explorer：探索的起点

选定一个对象类型后进入 **Explore perspective**，用**一组"图表 = 对某个属性的聚合"**来搜索和筛选数据：在图表上点某个值/拖某个范围，就构建出一个 **object set（对象集）**；对关联对象类型（linked object type）的图表可以按关联属性筛。探索结果可以**保存复用**（保存 Exploration / 对象列表）。右上角有 **Actions / Open In / Export** 三类按钮，把探索出的对象集"施加动作 / 带去别的应用 / 导出"。

### 2.3 Contour / Quiver 分析与报表构成

Foundry 的分析侧还有 Contour（点选式分析管线）、Quiver（时序/交互分析）等工具用于深度分析。而"报表"在 Workshop 里不是一个单独控件，而是**由 widget 组合而成**：一张典型报表 = 顶部若干 **Metric Card（KPI 卡片）** + 中部 **Chart / Pivot Table（图表/透视表）** + 明细区 **Object Table（对象表格）** + 侧边 **Filter List（筛选器）**。报表"显示什么字段"因此完全由这些 widget 各自的字段配置决定——这正是下一节的重点。

### 2.4 Control Panel：管理者的集中控制台

Control Panel 是 Foundry 的集中管理界面（`Cmd/Ctrl+J` 全局搜索），把**安全、资源管理、用例生命周期、审计**统一到一处。权限分**两级**，各有独立管理页：

- **Enrollment（企业级）**：authentication、networking/egress、retention、support、container governance。
- **Organization（组织级）**：application access、workspace、logging、email admin、user/group visibility、Workshop config。

---

## 三、字段级清单（重点）

本节是全篇硬核部分：一个操作应用/报表**具体显示哪些字段、支持哪些交互**，以及管理者 Control Panel **具体能看到什么**。枚举、上限数字、字段名尽量照原样保留，供"照着实现"。

### 3.1 Object Table（最能代表"操作应用"的字段规格）

**变量**
- 输入变量：Object set。
- 输出变量：**Active object**（当前高亮行）、**Selected objects**（开启多选后）、**右键对象**（供自定义右键菜单用）。

**可加的列类型**
- 标准属性（standard property）
- **Linked object properties**：沿 Link 展示关联对象的属性
- **Time series properties**：带 transform + summarizer（如 last value / average），可画 sparkline
- **Function-backed columns**：由 Function 派生的列，入参 `ObjectSet<ObjectType>`，出参 `Map / Record / dict`，可返回含多字段的自定义类型
- **URL Link columns**：参数化超链接
- **Custom Type / Struct / Array** 列
- **Combine multiple object types**：多种对象类型同表展示，或分 tab 展示

**每列配置**
- Conditional Formatting（条件着色规则：**整格 vs 仅文字**着色）
- Value Formatting（数字格式 / compact 紧凑 / 小数位）
- Column Sizing + 冻结列
- Display Names（自定义表头）
- Wrapping（换行）

**表级配置项（确切名称）**
- Number of lines to display per row（每行显示行数）
- Enable value wrapping（值换行）
- Number of frozen columns（冻结列数）
- Fit columns horizontally（水平铺满）
- Enable narrow headers（窄表头，50px → 30px）
- 自定义 "No value" 文案
- Show security markings（显示安全标记）
- Default sort(s)（默认排序，可多字段、含隐藏列）
- Enable multi-select（启用多选）
- Disable active object auto-selection（禁用自动选中当前行）
- On active object selection（选中行时触发事件）
- Empty state message（空态文案）
- Variable-backed column visibility（用 string array 变量控制哪些列可见）
- Hide column configuration（隐藏列配置入口）
- Scenarios support（场景/推演支持）

**行内编辑（Enable inline editing）**
- 把某个 action 的参数映射到列（下拉选择），点 "Edit table" 进入编辑态。
- 暂存上限：**普通 action ≤ 200 行；function-backed action ≤ 20 行**。
- 支持撤销 + 一键提交。
- 前提：本体里要有 "Modify object" 规则的 action，参数须为原生类型且来自 "from parameter"。

**右键菜单 / 导出**
- Enable export to CSV：**≤ 10,000 行**
- Enable export to Excel：**≤ 200,000 行**
- Customize right-click menu：自定义右键 action

### 3.2 Filter List（筛选器规格）

**变量**
- 输入：Object set。
- 输出：**object set filter 变量**（既捕获当前筛选条件供下游 widget 用，也用于设默认筛选值）。

**筛选组件类型**
- Keyword search（关键词，支持 **AND / OR / NOT + 括号**布尔语法）
- Histogram（数值/日期分布，选桶或拖范围）
- Single-select dropdown（单选下拉）
- Multi-select dropdown（多选下拉）
- Distribution chart（分布图）
- Single date picker / Multi-date picker（单/多日期选择器）
- Timeline（时间轴）

**配置**
- Add filter（选可筛属性）
- Allow user to add/remove filters（是否给用户 "Add filter" 按钮）
- Layout（**垂直滚动 vs 横向 pills**；pills 点开为 popover）
- Linked property filtering（"Has Link" 选项 + 分组/内联展示）
- Default values（在 filter 输出变量上设默认值）

### 3.3 Metric Card（报表/KPI 卡片规格）

**显示字段**
- **Primary metric value**（主指标值，绑 String / Number 变量）
- **Label**（顶部文案）
- **Description**（hover 时的 tooltip）
- **Secondary metric**（下方次值）
- **Sparkline**（时序历史迷你图）

**配置**
- Value type（String / Number）+ 变量绑定
- Numeric formatting（小数 / 前后缀）
- Conditional formatting（阈值规则着色）
- Sparkline：Time series set 变量 + Time range（**All time / Last hour / Last day / Last week / 自定义**）+ baseline + 位置（并排 / 堆叠）
- Layout：**Card / Tag / List**；metric size = **Compact / Regular / Large**
- Interactive metric（点卡片触发 command / action / event）
- 条件可见

### 3.4 Object Explorer 的图表聚合类型（全列表）

| 图表类型 | 适用属性 | 说明与聚合 |
| --- | --- | --- |
| **Listogram** | 非数值属性（String/Boolean/Array） | 显示值 + 计数或数值聚合（如 average）；可配聚合类型与排序；选择时下拉选"保留/排除" |
| **Pie Chart** | 布尔 / 字符串属性 | 饼图 |
| **Histogram** | 数值 / 日期属性 | 自动分桶，选桶或拖自定义范围（底部可编辑起止） |
| **Grid Plot** | 二维 | X 轴一属性 + Y 轴 "Group By" 属性；Ctrl/Cmd+click 连续多选 |
| **Single Statistic** | 单数值属性 | 聚合 Sum/Average/Min/Max/Count/Unique Count；**不能用于筛选** |
| **Statistics Table** | 数值 + 分组属性 | 按另一属性分组的数值聚合（Sum/Min/Max/Average/Count），可排序 |
| **Cluster Map** | geopoint | 气泡大小 = 计数/聚合，点气泡筛选 |
| **Choropleth Map** | 带地理 typeclass 的文本属性 | typeclass: `countries / us_states / us_counties / us_zip_codes`；可配聚合与色阶 |

**聚合选项全集**：Sum / Average / Min / Max / Count / Unique Count。

**右上三类按钮**
- **Actions**：对当前/选中对象做 writeback。**选中 > 1000 对象时 Action 不可用**；有选中集则传选中集，无选中则整个对象集直接传入 action 表单并智能预填参数。
- **Open In**：把当前 exploration 带到其他平台应用（目标取决于 workspace 配置）。
- **Export**：导出/复制 object IDs 到剪贴板、导出 Excel 等。

### 3.5 Control Panel——管理者具体看什么（用户 / 角色 / 资源 / 活动 / 健康）

#### A) 安全 & 访问（Security / Access）

- **Authentication**：SAML（Entra ID / Okta / 自定义）、OIDC、MFA 策略、user directory、intake forms、IdP 测试与 host 设置。
- **Users / Groups**：用户目录、组与角色分配、user/group visibility 设置。
- **Roles（角色）**：
  - 默认角色：**Owner / Editor / Viewer / Discoverer**（另有上下文角色如 Ontology Owner/Editor、Marketplace Installation Editor/Viewer）。
  - 角色 = **一组 operations（细粒度权限）**，例如 `stemma:mutate-default-branch`（Change default branch）、`stemma:mutate-branch`（Change branch）。在某资源上授予某角色 = 授予该资源及其子资源上的这组 operations。
  - **自定义角色**：Platform/Foundry Settings → Roles → New Role → 命名 → 可继承已有角色 + 从可选列表勾选 operations（示例：`Merger = Viewer + merge operations`；`Supporter = 可管 issue 但不看 metadata`）。
  - 只有 **Organization administrator** 才有 "Manage roles and role sets" 权限。
- **Organizations & Spaces**：组织/空间管理。
- **Networking & Egress**：cloud identities、域名/证书、CORS、egress（direct / AWS/Azure private link）、egress 证书、VPN ingress、container governance、connected hubs。

#### B) Resource Management（资源 / 健康）

> 位于 Support workspace 的 Application access，需要有 Resource management 应用访问权。

- **Usage types（4 类计量）**：

  | 计量类型 | 单位 | 说明 |
  | --- | --- | --- |
  | **Foundry Compute** | compute-seconds | 细分 Parallelized batch / interactive / continuous compute；由 core-seconds × 内存/核比推算；按 UTC 完成时间归因 |
  | **Query Compute-Seconds** | compute-seconds | 对 Ontology / Timeseries 索引存储的按需查询 |
  | **Ontology Volume** | GB-months | 索引数据存储；按小时粒度记录 |
  | **Foundry Storage** | GB-months | 非 Ontology 转换层的通用存储 |

- **Budgets（预算）字段**：
  - **Scope**（All usage / 指定 Usage account）
  - **Frequency**（Monthly / Quarterly / Yearly / Non-recurring）
  - **Budgeted amount**（货币值）
  - **Start date**（非周期预算另需 end date）
  - **Description**（可选）
  - **Notification thresholds**（占预算的百分比阈值）
  - **Users to notify**（Foundry / email）
  - **行为**：**仅追踪 + 告警，不硬性阻断**（不 block 花费）；通知有延迟（**可达 26h**，实际触发百分比可能高于设定值）。

- **Monitors（监控）**：绑定 budget，订阅者在预估用量接近预算时收到通知。
- **Resource Queues**：FIFO 队列，申请 vCPU / vGPU，可守护 **Job compute（batch transforms）/ Continuous compute / Session compute（交互等待型）**。
- 另有：Project usage tracking、Anomaly detection、Approvals（审批台）、Upgrade assistant。

#### C) 用户活动 & 审计（Activity / Health）

- **"Analyze user activity metrics"** 页：看用户活动指标。
- **Audit（audit.3 schema）**：从"事件型"转为"**类别型（category）**"。

  **每条审计记录的顶层字段（26 个，确切名）**：

  | 字段 | 含义 |
  | --- | --- |
  | `time` | RFC3339Nano UTC 时间戳 |
  | `eventId` / `logEntryId` / `sequenceId` | 三个 uuid |
  | `name` | product_endpoint 格式的事件名 |
  | `product` / `productVersion` / `producerType`(SERVER\|CLIENT) / `service` / `stack` / `environment` | 产品/服务/环境信息 |
  | `host` / `origin` / `origins` / `sourceOrigin` | 网络来源 |
  | `uid`(UserId) / `users`(set<ContextualizedUser>) | 用户；**注意当前 pipeline 只填 uid，userName/first/last/realm/groups 不填，需下游对 user directory 做 lookup 富化** |
  | `orgId` | 组织 ID |
  | `sid`(SessionId) / `tokenId` / `traceId`(Zipkin) | 会话 / 令牌 / 链路追踪 |
  | `userAgent` | 客户端 UA |
  | `categories`(set<string>) | 本条命中的审计类别 |
  | `entities` | 涉及的资源 |
  | `requestFields`(map) | 调用参数 |
  | `resultFields`(map) | 返回/派生信息 |
  | `result`(AuditResult) | **SUCCESS / ERROR / UNAUTHORIZED …** |

  **审计类别（category，每条必挂一个或多个，各自带必填 requestFields/resultFields）**：

  - `dataLoad`(loadedResources)
  - `dataExport`(downloadedResources, downloadedSize)
  - `dataImport`(importedFilename, importResourceId, importedFileType)
  - `dataCreate`(createdResources)
  - `dataDelete`(deletedResources)
  - `dataTransform`(transformTargets, transformDescription)
  - `dataSearch`(dataSearchQuery, dataSearchResults)
  - `dataMerge`(resourcesToMerge, mergedResult)
  - `dataShare` / `dataShareCreate` / `dataShareDisable`
  - `managementPermissions`(resourcesWithPermissionsChanges)
  - `userLogin`(loginUserId)
  - `authenticationCheck`(authenticationCheckResult)
  - `authorizationCheck`(authorizationCheckOperations, ...SucceededTargets, ...FailedTargets)
  - `managementUsers`(managedUserIds)
  - `managementGroups`(groupPatches)
  - `managementTokens`(managedTokens)
  - `logicAccess` / `logicCreate` / `logicUpdate` / `logicDelete`
  - `appConfigAccess` / `appConfigCreate` / `appConfigUpdate` / `appConfigDelete`
  - `metaDataAccess` / `metaDataCreate`
  - `requestCreate` / `requestApprove` / `requestExecute`
  - `llmInference`(llmInferenceContext, llmInferenceInputs, llmInferenceResponses)
  - `auditDataRedact`

  **审计 API**：`audit-v2` 的 List Log Files 等；也可在 Organization settings → Configure logging 配置日志。

  **示例 audit.3 JSON**（据字段结构推导，官方未给实例，落地需实测校准）：

  ```json
  {
    "time": "2026-06-25T08:12:03.123456789Z",
    "eventId": "b1a...", "logEntryId": "c2d...", "sequenceId": "e3f...",
    "name": "objectdb_searchObjects",
    "product": "object-storage", "productVersion": "1.842.0",
    "producerType": "SERVER",
    "uid": "u-0123", "orgId": "ri.multipass..org.abc",
    "sid": "sess-789", "userAgent": "Mozilla/5.0 ...",
    "categories": ["dataSearch"],
    "entities": ["ri.ontology.main.object-type.SalesOrder"],
    "requestFields": {"dataSearchQuery": "SO0001"},
    "resultFields": {"dataSearchResults": 1},
    "result": "SUCCESS"
  }
  ```

---

## 四、映射到DataSteward 栈（我们怎么复刻）

我们的栈：StarRocks 数仓（OLAP）/ PostgreSQL 源（OLTP）/ Flink CDC / Neo4j 图 / pgvector / 只读 MCP + JSONL 审计 / 无头 Claude / Streamlit 多页治理台。

**先立铁律**：Palantir "读走对象、写走 Action、每步留痕"。我们**已做到**"读走只读 MCP（3 个只读工具）+ 每步 JSONL 留痕"，**缺"写走 Action"**。今天的切片可**先只读**；愿景是加一条**受控写回路径**（审批 + 留痕的 Action），而不是直接改库。

### 4.1 现有 8 页与新页的对应

Palantir 的三大应用面（Workshop 操作应用 / Object Explorer / Control Panel）在我们这里对应治理台的三组页面。以下把每个 widget 的字段规格落到具体的 Streamlit 控件：

#### (1) Workshop 操作应用 → "对象工作台页"

| Palantir widget | Streamlit 实现 | 字段/交互映射 |
| --- | --- | --- |
| **Object Table** | `st.dataframe` / `st.data_editor` | `column_config` 对应列格式/冻结/宽度；选中行 = **Active object**（存 `st.session_state`）；多选 = **Selected objects**；CSV/Excel 导出用 pandas，照抄 **10k / 200k 行**上限做守护 |
| **Filter List** | `st.sidebar` 内一组控件 | 按属性放 `selectbox`(single) / `multiselect`(multi) / `slider`(histogram 范围) / `date_input`(single/multi) / `text_input`(keyword)；筛选状态存 `session_state` = 我们的 **object set filter 变量**；对 SalesOrder / Material / Supplier 等表各建一份 |
| **Metric Card** | `st.metric` | value + label + delta 对应 primary/secondary metric；阈值着色用 `st.markdown` 自定义；KPI 例：**待发货订单数、缺料 SKU 数** |
| **Inline Action / Button Group** | `st.button` 触发受控 Action | 先在治理台弹审批表单 → 通过后经独立写回接口（PoC 先写回 PostgreSQL 源，Flink CDC 再同步进 StarRocks，形成 writeback 闭环）→ 每次 Action 追加一条 JSONL（对应 audit.3 的 `requestCreate/Approve/Execute` + `dataTransform`） |

> 具体 KPI 可用平台里稳定的测试 ID 演示：`SO0001`（需 `M0046`×265）、`M0001`（库存 12 @ `W02`）、`S001`（PO `PO0021`）。

#### (2) Object Explorer → "探索页" + Neo4j 图谱页

- **图表聚合**（Listogram / Histogram / Statistics Table / Single Statistic）→ 对 StarRocks 跑 `GROUP BY` 聚合 + `st.bar_chart` / `st.plotly`；点桶筛选 = 把选中值写回 filter 变量再重查。
- **Cluster / Choropleth Map** → 若有地理字段用 `st.map` / `pydeck`（当前数据无地理维度，暂缓）。
- **Actions / Open In / Export 三按钮** → 治理台"对象集操作区"：
  - **Actions** = 受控写回；
  - **Export** = 下载（照搬 Excel/复制 object IDs）；
  - **Open In** = 跳到 Neo4j 图谱页（把当前对象集 ID 传给图查询做 Search-Around 多跳）。
  - **1000 对象上限**照搬为写回批量守护。

#### (3) Control Panel → "管理者页"（本篇重点，管理者视角）

- **角色 / 权限**：用一份 `roles.yaml` 定义 **Owner / Editor / Viewer / Discoverer** + operations 列表（我们没有 Foundry 那套完整 ACL，先做"哪个角色能看哪些表 / 能否触发 Action"的轻量映射），治理台展示 **"用户-角色-资源"矩阵**。
- **Resource Management → 用量页**：把 Palantir 的 compute-seconds 换成我们可测的量：**MCP 查询次数/耗时、agent token 用量、StarRocks 查询耗时、Flink CDC 延迟**。**Budgets 模型直接照抄字段**（Scope / Frequency / Amount / Thresholds% / Users to notify）做"用量预算 + 阈值告警"（超阈值发钉钉）；Monitors = 定时任务检查。Resource Queues 暂不需要（无多租户抢占）。
- **活动 / 审计 → 审计页**（我们最该照抄的）：把现有 `audit_log.jsonl` 字段对齐 audit.3——至少加 `time / eventId / sid`(= session_id) `/ name / categories / result`(SUCCESS\|ERROR\|UNAUTHORIZED) `/ requestFields / resultFields / entities / uid`。category 用**简化子集**：
  - `dataSearch`（MCP SQL 查询）
  - `dataLoad`
  - `dataExport`
  - `authorizationCheck`
  - `requestCreate / requestApprove / requestExecute`（写回 Action）
  - `llmInference`（agent 每次调用，记 inputs / responses）
  
  治理台**按 `session_id` 回放任务链**（已有能力）正好对应 Palantir 按 `sid / traceId` 串联。由此 `audit_log.jsonl ↔ agent_session.jsonl` 的关联升级为"**category 化 + 结果码化**"的可查询审计。

### 4.2 数据流对齐

Palantir 的 **Ontology Volume / Storage 两级存储** ≈ 我们的 **StarRocks（查询/OLAP）+ PostgreSQL（源/OLTP）**；**writeback 回源** = 我们**写 PostgreSQL → Flink CDC → StarRocks**，天然实现 Palantir "Action 经集成回写源系统"的闭环。

### 4.3 最小今天切片

治理台加 3 个页：

1. **对象工作台**（Object Table + Filter List + Metric Card，只读）
2. **探索页**（GROUP BY 图表 + 跳 Neo4j）
3. **管理者页**（角色矩阵 + 用量预算告警 + category 化审计回放）

audit.3 的字段/类别子集落到 JSONL。**写回 Action 留作愿景下一切片。**

复刻优先级：widget 只需覆盖 **Object Table / Filter List / Metric Card / Button Group / Chart** 这 5 个高频件即可。

---

## 五、Open questions

1. **audit.3 JSON 实例未知**：官方未给完整实例，上面的示例据字段结构推导；真实字段的确切嵌套/命名（如 `entities` 是纯 RID list 还是带类型的对象）需实测一条真实日志校准。我们 JSONL 可先按此设计，接入后再对齐。
2. **默认角色与 operation 全集**：Foundry 是否只有 Owner/Editor/Viewer/Discoverer 官方未明确穷举，operation 全集（远不止 `stemma:*` 两个示例）也未穷举。我们 `roles.yaml` 只能先取业务够用的最小子集，无法 1:1 复刻全部 operation 命名。
3. **Open In / Export 目标清单**：随 workspace 配置而变，官方未给固定列表（已确认 Excel + 复制 object IDs，CSV 未在该页确认）。我们映射为"跳图谱页 / 下载"即可。
4. **预算告警策略是可自主决策点**：Palantir Budgets 只告警不阻断、通知延迟可达 26h 是其 SaaS 计费特性；我们自建用量告警可做成**实时 / 可选硬阻断**。
5. **compute-seconds 的等价计量单位**：我们栈没有官方对应，需自定义（MCP 查询耗时 + agent token 数 + StarRocks CPU 时）。选哪个作"预算主指标"需和用户确认。
6. **widget 目录随版本增减**：复刻只需覆盖上面 5 个高频件，其余按需补。
7. **writeback 闭环的 CDC 延迟与 UI 反馈**：`写 PostgreSQL → Flink CDC → StarRocks` 的延迟，以及"写入已生效"的 UI 反馈策略，需实测后决定。

---

## 六、来源

- Workshop / widgets（概念与部件规格）
  - https://www.palantir.com/docs/foundry/workshop/concepts-widgets
  - https://www.palantir.com/docs/foundry/workshop/widgets-object-table
  - https://www.palantir.com/docs/foundry/workshop/widgets-filter-list
  - https://www.palantir.com/docs/foundry/workshop/widgets-filtering
  - https://www.palantir.com/docs/foundry/workshop/widgets-object-dropdown
  - https://www.palantir.com/docs/foundry/workshop/widgets-metric-card
  - https://www.palantir.com/docs/foundry/workshop/widgets-pivot-table
  - https://www.palantir.com/docs/foundry/workshop/overview
  - https://www.palantir.com/docs/foundry/app-building/overview
- Object Explorer
  - https://www.palantir.com/docs/foundry/object-explorer/explore-charts
  - https://www.palantir.com/docs/foundry/object-explorer/apply-actions
  - https://www.palantir.com/docs/foundry/object-explorer/filter-results
  - https://www.palantir.com/docs/foundry/object-explorer/getting-started
- Administration / Control Panel
  - https://www.palantir.com/docs/foundry/administration/control-panel
  - https://www.palantir.com/docs/foundry/administration/overview
  - https://www.palantir.com/docs/foundry/administration/configure-logging
- 角色与安全
  - https://www.palantir.com/docs/foundry/platform-security-management/manage-roles
  - https://www.palantir.com/docs/foundry/security/projects-and-roles
- 资源管理
  - https://www.palantir.com/docs/foundry/resource-management/overview
  - https://www.palantir.com/docs/foundry/resource-management/usage-types
  - https://www.palantir.com/docs/foundry/resource-management/budgets
  - https://www.palantir.com/docs/foundry/resource-management/monitors
  - https://www.palantir.com/docs/foundry/resource-management/resource-queues
- 审计
  - https://www.palantir.com/docs/foundry/security/audit-logs-overview
  - https://www.palantir.com/docs/foundry/security/audit-log-categories
  - https://www.palantir.com/docs/foundry/api/audit-v2-resources/log-files/list-log-files
