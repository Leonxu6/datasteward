# Palantir Foundry / AIP 实装级复刻 Spec

> **本文定位**：供工程团队"照着做"的实装规格，而非概念综述。9 个维度（连接器 / 转换 / 本体 / 权限 / 审计 / 血缘 / 数据健康 / 报表&Control Panel / AIP-Action）全部挖到字段名、枚举、上限数字、JSON/接口形态的粒度。所有对抗验证发现的更正已吸收进正文（关键更正在每节 **⚠ 更正** 标注）。
>
> **本文不重复代码**：现有栈已实现的部分只指出落点文件；本文聚焦"要新增/改成什么形态"。
>
> **今天的切片 vs 愿景**：每个子系统都区分「PoC 今天可交付」与「生产愿景」。当前栈是**全只读**（MCP 3 工具 + JSONL 审计），最大缺口是 **governed Action 写回层** 与 **Markings 沿血缘传播**。
>
> **我们的栈**：StarRocks（OLAP 数仓）/ PostgreSQL（OLTP 源）/ Flink CDC（增量同步）/ Neo4j（图/血缘）/ pgvector（语义检索）/ 只读 MCP 连接器 + JSONL 审计 / 无头 Claude（`claude -p`）/ Streamlit 治理台。单机 compose 编排。

---

## 目录

1. [分层架构总览与数据流](#1-分层架构总览与数据流)
2. [逐子系统数据模型与接口](#2-逐子系统数据模型与接口)
   - 2.1 [连接器（Data Connection）](#21-连接器data-connection)
   - 2.2 [转换 / 数据集分层（Transforms & Datasets）](#22-转换--数据集分层transforms--datasets)
   - 2.3 [Ontology（对象/属性/链接/Action/Function）](#23-ontology对象属性链接actionfunction)
   - 2.4 [权限（Markings/角色/行列/写回）](#24-权限markings角色行列写回)
   - 2.5 [审计（audit.3 分类 + JSON schema）](#25-审计audit3-分类--json-schema)
   - 2.6 [血缘（节点/边 + 列级 + 安全传播）](#26-血缘节点边--列级--安全传播)
   - 2.7 [数据健康（监控目录：信号/阈值/告警）](#27-数据健康监控目录信号阈值告警)
   - 2.8 [报表 & Control Panel（字段级清单）](#28-报表--control-panel字段级清单)
   - 2.9 [AIP-Action（agent 执行与治理化写回）](#29-aip-actionagent-执行与治理化写回)
3. [我们栈上的落地映射与取舍](#3-我们栈上的落地映射与取舍)
4. [关键决策点与 open questions](#4-关键决策点与-open-questions)
5. [关键来源 URL](#5-关键来源-url)

---

## 1. 分层架构总览与数据流

Palantir Foundry 是一条"**声明式、版本化、血缘自动、治理内嵌**"的数据操作系统。六层，每层的产物都是下一层的输入，且**权限/血缘/审计横切贯穿全部六层**：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 横切治理面（贯穿全部六层，不是单独一层）                                        │
│  • 权限：Mandatory(Markings/Orgs/Classifications) AND Discretionary(Roles)      │
│  • 审计：audit.3，每个动作至少一个 category，append-only，traceId 串联           │
│  • 血缘：Dataset 抽象的副产品，自动生成；Markings 沿血缘并集传播                 │
│  • 数据健康：Health Checks（资源级）+ Monitoring Views（运行面）+ 构建期门禁      │
└─────────────────────────────────────────────────────────────────────────────┘

① 连接器层 Data Connection
   Source(连接定义+凭证+网络策略+源打标) → Connector(集成器,~200+) → Sync(batch/
   incremental/streaming/media/file，单事务写) → 落 raw Dataset。Export 反向推回。
   Virtual table 不落地直查(Snowflake/BigQuery/Databricks/Iceberg/Delta) + 谓词下推。
        │  每次 sync = 输出 Dataset 的一个不可变原子事务
        ▼
② raw/refined 层 Datasets & Transforms（三段式项目）
   raw(尽量原样) → clean(显式 CAST) → canonical(可复用) → 喂本体。
   @transform/@transform_df 声明 Input()/Output() → 框架自动推导 DAG → Build 产出
   新事务。@incremental 增量。Data Expectations(Check on_error=FAIL/WARN) 构建期门禁。
        │  canonical Dataset 提升为对象类型（1 datasource ↔ 1 object type）
        ▼
③ Ontology 语义层（名词 + 动词）
   名词：Object Type / Property / Link Type（语义层）
   动词：Action Type / Function（+ Dynamic Security，动力学层）
   OSv2 存储：Object Data Funnel → OMS(元数据) + Object Databases(自研索引) → OSS(读/
   搜索/Search-Around) + Actions Service(写)。OSDK 生成强类型 SDK。
        │  对象/链接 = 消费层与 AI 的统一访问抽象
        ▼
④ 消费层 Workshop / Object Explorer / Reports
   Object Table / Filter List / Metric Card / Chart …；Explorer 图表聚合探索建对象集。
   只读仪表盘（看/筛/导） vs 操作应用（看 + 经 Action 写回改变现实）。
        │
        ▼
⑤ Action / 写回层 AIP-Action
   Action Type = 事务式编辑：Parameters + Rules + Submission criteria + Side effects +
   Permissions。写必过 validate(校验+权限+提交条件) → apply 落库 + 留 lineage。
   Side effect: Notification / Webhook(回写外部 ERP/MES) / Schedule。
        │
        ▼
⑥ AI 消费面 AIP（Logic / Agent Studio / Evals）
   每条消息确定性检索(Ontology/Document/Function context) 注入 system prompt → LLM 经
   prompted/native tool calling 选工具 → Object Query(读)/Function(算)/Action(写) →
   写走 validate/apply 窄门。AIP Evals 离线回归。AI 与人走同一套权限（agent 权限 ≤ 调用者）。
```

**端到端数据流（一次"确认发货"为例）**：
1. Flink CDC 从 PostgreSQL U8 源把 `sales_order` / `inventory` 增量同步到 StarRocks raw（① 连接器）。
2. dbt/transform 把 raw → clean（显式 CAST）→ canonical `fct_sales_order`（② 转换）。
3. canonical 表提升为 `SalesOrder` 对象类型，链到 `Material` / `Customer`（③ 本体）。
4. Streamlit 对象工作台展示待发货订单（④ 消费）。
5. 用户点"确认发货" → `shipOrder` Action：validate 校验"库存 ≥ 需求" → apply 写回 PostgreSQL 源（⑤ 写回）。
6. 无头 Claude 也能经 governed 写 MCP 调同一个 `shipOrder`，全程 audit.3 留痕（⑥ AI）。
7. 写回 PostgreSQL → Flink CDC 再同步回 StarRocks，形成闭环；血缘图记录这条边，Markings 沿边传播。

---

## 2. 逐子系统数据模型与接口

### 2.1 连接器（Data Connection）

#### 数据模型：四对象 + Virtual table

| 对象 | 定义 | 关键字段 |
|---|---|---|
| **Source** | 外部系统的连接实例 | `source_id`、连接参数(URL/host/port/region)、凭证、`network_egress_policy`、`markings[]` / `organizations[]`（源打标）、`runtime`(foundry_worker / agent_worker) |
| **Connector / Source type** | 针对某类系统的集成器（官方 ~200+，全列表见下） | 未列出的关系库统一走 `JDBC (custom)`；通用协议 REST/GraphQL/OData/Generic |
| **Sync** | 真正搬数的动作 | 类型：`batch` / `incremental` / `streaming`(Flink) / `media set` / `file`。每次 run = 输出 Dataset 单事务，失败 abort 不留半截 |
| **Export** | 反向把 Foundry 数据推回外部 | 双向 |
| **Virtual table** | 不落地、按查询直读外部 | 源：Snowflake / BigQuery / Databricks / 云存储 Iceberg&Delta；backed 时可 compute pushdown（谓词下推）。`@incremental` 在 pushdown 下**不支持** |

#### 连接架构（两种运行时）

- **Foundry worker + agent proxy（推荐）**：agent 向 Foundry 发起 websocket；数据连接与计算由 Foundry worker（隔离容器、弹性伸缩）执行。agent 只当纯网络隧道，不做数据处理。升级/扩容/补丁集中在 Foundry。
- **Agent worker（legacy）**：agent 常驻私网，出站单向 HTTPS 轮询 Foundry 取任务，自己执行、结果经同一连接回传。
- **网络方向**：Foundry 不向外部系统发起入站；agent 主机需对目标外部系统有出站连通性。
- **agent 运行时**：JVM heap 在 agent settings 页配置，默认 1 GB。

#### 凭证保管

- **agent worker 模式**：录凭证时在**浏览器里用分配给该源的每个 agent 的公钥加密**后再送 Foundry；加密凭证存 Foundry，只有对应 agent 用私钥能解。
- 外部系统凭证用 **AES-128-GCM** 加密，密钥存 agent 上；执行时 agent 从 Foundry 取加密凭证、本地解密、**用完自动从内存删除**。
- agent 集合变更需重录凭证。
- **认证方式**：用户名/密码、OAuth 2.0 / OIDC、API key/token、云原生 IAM 角色。REST 源支持 OAuth Client Credentials（配 token endpoint 域 + resource API 域，client_id/client_secret 作为 additional secrets 存源上）。

#### 源打标 + 网络隔离（连接治理）

- **Markings / Organizations** 加在 Source 上，**传播到该源 syncs 产出的所有 Dataset**——用户不具备源上全部 Markings/Organizations 就看不到任何下游 Dataset 数据。
- **network egress policy**：Foundry worker 源建源时**必须**指定；客户自管 egress 用容器网络（Cilium/eBPF）对单个 workload 施防火墙规则；wildcard（`*.domain.com`）可 allowlist 整个子域。

#### 增量 sync（stateful，APPEND 风格）

- **Single field 模式**：目标列 >= 已导入最大值时导入。须提供单调递增列（timestamp / id / LSN）+ 初始值；平台跟踪已同步最新值。
- **JDBC 写法**：SQL 里加**一个** `?` 占位符（仅可用一个），例 `SELECT * FROM orders WHERE id > ?`。首跑带初始值。
- **APPEND vs SNAPSHOT**：入 Foundry 数据应由 APPEND 事务组成（只带新数据）；源不支持增量时用 SNAPSHOT 整表替换。
- 事务元数据：Dataset 事务历史 → Custom Metadata → `incrementalMetadata` 块。
- **版本化源**（Delta/Iceberg）能检测变更、只触发必要的下游 build。

#### 连接器 / Source type 分类全列表（~200+）

<details><summary>展开全列表（官方口径，随版本变，以 docs.palantir.com/available-connectors 当期页为准）</summary>

- **数据库/数仓**：AlloyDB, Amazon DynamoDB, Amazon Redshift, Apache CouchDB, Apache HBase, Apache Hive, Apache Phoenix, Azure Cosmos DB, Azure Synapse, Azure Table Storage, BigQuery, Cassandra, CockroachDB, Couchbase, Databricks, Db2, EnterpriseDB, Google Spanner, Greenplum, HDFS, IBM Cloud Data Engine, MarkLogic, Microsoft Access, Microsoft SQL Server (+Analysis Services), Oracle Database, PostgreSQL, Presto, Redis, SAP HANA XSA, SingleStore, Snowflake, Spark SQL, SybaseIQ
- **对象/文件存储**：Agent-level filesystem, Amazon S3, ABFS, Google Cloud Storage, IBM Cloud Object Storage, OneLake, SFTP, SMB, FTP/FTPS, Directory
- **流/消息**：Amazon Kinesis, Apache Kafka, Google Pub/Sub, Twilio
- **ERP/财务**：ADP, Avalara, Certinia, Epicor Kinetic, Oracle Fusion Cloud (Financials/HCM/SCM), QuickBooks, SAP ERP, SAP SLT, SAP Ariba, SAP Business One, SAP ByDesign, SAP Cloud for Customer, SAP Fieldglass, SAP Concur, Xero, Zoho Books, Tally, Acumatica, MS Dynamics GP/NAV/365 Business Central
- **CRM/销售**：Bullhorn, Highrise, HubSpot, MS Dynamics CRM/365, Outreach, Pipedrive, Salesforce, Salesloft, SugarCRM, SuiteCRM
- **营销/广告**：Act-On, Adobe Analytics, Adobe Commerce, Facebook Ads, Google Campaign Manager, LinkedIn Marketing, Marketo, Microsoft Ads/Bing, Salesforce Marketing Cloud, Snapchat Ads, Twitter Ads
- **HR**：Paylocity, SAP SuccessFactors
- **会计/支付**：Authorize.Net, Exact Online, FreshBooks, MYOB, PayPal, Reckon, Sage, Square, Stripe, TaxJar, Wave Financial, Zuora
- **项目/协作**：Asana, Basecamp, Monday, MS Planner/Project, Smartsheet, Trello
- **工单/支持**：Freshdesk, Jira Service Management, Zendesk
- **通信/协作**：Gmail, MS Exchange/Office365/Teams, Slack
- **文档/内容**：Confluence, DocuSign, MS OneNote/SharePoint
- **BI**：Tableau CRM Analytics, SAP BusinessObjects BI, MS Power BI XMLA
- **电商**：BigCommerce, eBay, Shopify, WooCommerce, WordPress, ShipStation
- **社媒**：Facebook, Instagram, LinkedIn, Pinterest, YouTube Analytics
- **目录/身份**：Azure AD, Google Contacts/Directory, LDAP, Directory
- **开发**：GitHub
- **协议/通用**：REST APIs, GraphQL, OData, JDBC (custom), Generic connector, RSS, Email
- **专用/工业**：PI System（OSIsoft 工业时序）, Veeva Vault, Palantir Foundry, SAS Data Sets/Xpt

</details>

---

### 2.2 转换 / 数据集分层（Transforms & Datasets）

#### 数据集与事务（版本化地基）

Dataset = 底层文件集合(常 Parquet) + schema(挂文件集合上的元数据) + 事务历史 + 可分支。每次写入 = 一个**原子不可变事务**。

| 事务类型 | 语义 | 用途 |
|---|---|---|
| `SNAPSHOT` | 整体替换当前视图全部文件 | 批管线；打断下游增量 |
| `APPEND` | 只加新文件、不改已有 | 增量管线基础 |
| `UPDATE` | 加新文件且可覆盖已有文件内容 | 部分分区更新 |
| `DELETE` | 删文件 | 保留期清理 |

- 状态：`OPEN` / `COMMITTED` / `ABORTED`。
- **view 解析规则**：从该时点前最近的 SNAPSHOT（无则最早事务）开始，SNAPSHOT/APPEND 加全部文件，UPDATE 加入并替换同名文件。
- 可像代码一样**分支**（默认主分支受保护）。

#### 分层（recommended project structure）

三段式项目，层级 `raw → clean → canonical → ontology`：

| 项目 | 输入 | 产出 | 关键约定 |
|---|---|---|---|
| **Datasource Project** | Data Connection sync | raw（尽量原样）→ clean | **即便 schema 推断对了，也要在 raw→clean 显式 CAST 列类型** |
| **Transform Project** | 一或多个 Datasource 的 clean | canonical（规范、可复用） | import 跨项目 |
| **Ontology Project** | Transform 的 canonical | 对象表 → 映射本体对象 | |

固定目录：`/clean` `/logic` `/output` `/analysis` `/scratchpad` `/documentation`(血缘图) `/datasets`。命名：两三词、`stg_`/`int_`/`dim_`/`fct_` 前缀。

#### 转换 API（transforms-python）

三个核心装饰器：
- `@transform`：最通用，函数收 `TransformInput`/`TransformOutput`，自己调 `.dataframe()` 读、`.write_dataframe()` 写；可注入 `ctx=TransformContext`（`ctx.spark_session` / `ctx.is_incremental`）。
- `@transform_df`：`return` 一个 DataFrame 即写出，Output 作第一个位置参数。
- `@transform_pandas` / `@transform_polars`：同形态。

声明类：`Input(path, branch=?, stop_propagating=?, stop_requiring=?)`、`Output(path, checks=?)`、`Markings(marking_ids, on_branches)`、`OrgMarkings(marking_ids, on_branches)`。

框架从"函数参数=输入 Dataset、返回值/Output=输出 Dataset"自动拼 DAG、拓扑排序、决定并行与增量范围。

#### @incremental 完整签名（照抄可用）

```python
@incremental(
    require_incremental=False,   # bool: True=不能增量就失败(除非从未跑过)
    semantic_version=1,          # int: 逻辑改到使旧输出失效时+1 → 强制全量重算
    snapshot_inputs=None,        # list[str]: 这些输入的 SNAPSHOT 不打断增量;支持 update/delete,每次全量读
    allow_retention=False,       # bool: True=retention 删除不打断增量
    strict_append=False,         # bool: True 且增量 → 底层事务强制 APPEND
    v2_semantics=False,          # bool: 官方建议设 True
)
```

**读模式** `input.dataframe(mode)`：
- `'added'`：增量跑=只返回新增/更新行；非增量/快照跑=返回整表（全部视为新）。
- `'current'`：两种跑法都返回本次全量。
- `'previous'`：增量跑=返回上次处理的输入/输出；首次或大改后为空 DataFrame（故 `output.dataframe('previous', schema)` 必须传 schema 构造空 DF）。

**写模式** `output.write_dataframe(df, mode)`：`'modify'`（增量默认，追加/更新）| `'replace'`（全量覆盖）。运行时用 `ctx.is_incremental` 分支。

**Foundry 决定跑增量的四项检查**：① 输入变更分析（只有 append-only vs 破坏性修改）② 输出血缘检查（输出上次由同一 transform 构建）③ 输入一致性（非快照输入的起始事务与上次匹配）④ semantic_version 未变。

#### Data Expectations（构建期门禁）

```python
import transforms.expectations as E
from transforms.api import Check, Output, transform_df

@transform_df(
  Output("/dm/dwd/sales_order", checks=[
    Check(E.primary_key("order_id"), "PK 唯一非空", on_error="FAIL"),
    Check(E.count().gt(0),          "非空表",       on_error="FAIL"),
    Check(E.all(
        E.col("qty").non_null(),
        E.col("qty").gte(0),
        E.col("qty").lt(1_000_000)), "数量合法域", on_error="FAIL"),
    Check(E.col("status").null_percentage().lt(0.01), "状态列近乎非空", on_error="WARN"),
    Check(E.schema(), "结构契约", on_error="FAIL"),
  ]))
def compute(...): ...
```

- `on_error`：`FAIL`（默认，abort 构建、回滚输出事务、脏数据不落下游）| `WARN`（放行但记警告，交 Data Health）。
- 列谓词 `E.col('c')`：`.non_null()` `.gt(x)` `.gte(x)` `.lt(x)` `.lte(x)` `.equals(x)` `.between(a,b)` `.null_count()` `.null_percentage()` `.distinct_count()` `.sum()`。
- 组合 `E.all(...)`；数据集级 `E.primary_key('a','b')` `E.count()` `E.group_by(...)` `E.schema()`。
- Pipeline Builder UI 目前内建 primary key + row count 两种，publish 后转为 health check。

#### 构建与调度（build / schedule / triggers）

- **Build** = 读输入某版本 → 跑转换 → 产出输出一个新事务；从声明自动推导依赖图、按拓扑序调度、只重算受影响下游。
- **Schedule 触发类型**：
  - 时间：cron。
  - 事件（4 种）：`New logic`（逻辑更新）、`Data updated`（有事务提交）、`Job succeeded`、`Schedule ran successfully`。
  - 复合：`AND trigger`（合取）/ `OR trigger`（析取）。
- 官方建议把 Data Connection sync 与其余 build 分开调度，以便只对 sync 做 force-build。

---

### 2.3 Ontology（对象/属性/链接/Action/Function）

五构件分两层：**语义层（名词）** = Object Type / Property / Link Type；**动力学层（动词）** = Action Type / Function（+ Dynamic Security）。

#### Object Type 对象类型

**必填**：ID（小写字母/数字/连字符，字母开头）、Display name、Plural display name、API name（PascalCase，1–100，NFKC，非保留字）、Backing datasource、Primary key property、Title key property。
**选填**：Description、Icon、Color、Groups、Aliases。
**硬规则**：**一个 datasource 只能背书一个 object type**。主键须**唯一 + 确定性（deterministic，跨构建稳定，否则用户编辑会丢失）**、基于列值而非随机/自增。
**状态枚举**：ACTIVE / ENDORSED / EXPERIMENTAL / DEPRECATED。**可见性枚举**：NORMAL / PROMINENT / HIDDEN。

一个完整 Object Type 定义（官方 Get Object Type V1 JSON）：

```json
{
  "apiName": "employee",
  "description": "A full-time or part-time employee of our firm",
  "primaryKey": ["employeeId"],
  "properties": {
    "employeeId": { "baseType": "Integer" },
    "fullName":   { "baseType": "String" },
    "office":     { "description": "…", "baseType": "String" },
    "startDate":  { "description": "…", "baseType": "Date" }
  },
  "rid": "ri.ontology.main.object-type.0381eda6-69bb-4cb7-8ba0-c6158e094a04"
}
```
> V1 用扁平 `baseType`；V2 `ObjectTypeV2` 用嵌套 `dataType.type`，并多出 displayName/pluralDisplayName/status/titleProperty/visibility/icon/aliases/datasources。

#### Property 属性

每属性可配：ID、Display name、Description、API name（camelCase，1–100）、Base type、Keys（是否 title/primary key）、Status、Visibility、Value formatting、Conditional formatting、Type classes、Render hints、Searchable、Sortable、RID（自动）。

**Base type 完整枚举**：
- 标量：`String` `Integer` `Long` `Short` `Byte` `Float` `Double` `Decimal` `Boolean` `Date` `Timestamp`
- 特殊：`Vector`(语义搜索) `Geopoint` `Geoshape` `Attachment` `Time series` `Media reference` `Cipher text` `Struct`
- **数组**：除 `Vector` 与 `Time series` 外所有 base type 均可作数组；`Map` 与 `Binary` 不可作 base type；OSv2 数组不允许 null 元素。

#### Value Type 值类型（base type 之上的语义约束，跨属性复用）

约束枚举：`Enum`(one of) / `Range`(min/max) / `Regex` / `RID` / `UUID`(String 专属) / `Uniqueness` / `Nested`(Array 专属) / `Element constraints`(Struct 专属)。

#### Link Type 链接类型（三种背书方式对应基数）

| 背书方式 | 基数 | 数据要求 |
|---|---|---|
| Object type foreign keys | one-to-one, many-to-one | 一侧外键属性 → 另一侧主键属性，无需额外数据集 |
| Join table dataset | many-to-many | 背书数据集含两侧主键两列（一列只映射一个主键） |
| Backing object type | many-to-one | 中间对象类型 + 两条 many-to-one 链 |

每侧字段：Display name、API name（小写字母开头、字母数字、同对象类型内唯一、1–100、NFKC）。

#### Action Type 动作（= 一次事务式编辑）

构件：**Parameters**（用户输入）、**Rules**（做什么变更）、**Submission criteria**（能否提交）、**Side effects**（副作用）、**Permissions**（谁能调）。

**Rules 全列表**：Create object / Modify object(s) / Create or modify object(s) / Delete object(s) / Create link(s)（仅 m-n）/ Delete link / **Function rule**（引用 Ontology edit 函数，**存在时不可配其他 rule**）/ 6 个 interface 变体（Create/Modify/Delete objects of interface、Create/Delete links on interface objects）。
- 属性赋值四法：`From parameter` / `Object parameter property` / `Static value` / `Current User·Time`。
- **非法组合**：删在增/改前、改在增前、同次创建两次——均禁止。
- 另有 `Notification rule`、`Webhook rule`（可配 edits 前/后执行）、`Schedule rule`。

**Submission criteria**（原 validations）= conditions + operators：
- 模板：`Current User`（检查 user id / 组 / multipass 属性）、`Parameter`。
- 单值算子：`is` / `is not` / `matches`(正则) / `is less than` / `is greater than or equals`。
- 多值算子：`includes` / `includes any` / `is included in` / `each is` / `each is not`。
- 逻辑 `All`/`Any`/`None` 可嵌套；每根条件带失败提示语。
- 可引用：参数值 / 用户属性 / 对象属性值 / 静态值。
- **不支持** attachment 与 object set 参数。

**Side effects**：Notification / Webhook（可配 pre/post-edit，写回外部）/ Schedule（触发构建）。

#### Function 函数

TS/Python 编写任意复杂逻辑。Function-backed Action：TS v1 用 `@OntologyEditFunction` 装饰器；TS v2 与 Python 用 edits API 直接 create/modify/delete。适合"改多个关联对象/跨对象计算/建多对象+建链"。受双重限额（action 限额 + function 超时/资源）。

#### OSv2 存储与硬限额

- 组件：Object Data Funnel（编排写入）、OMS（元数据）、Object Databases（自研增强索引）、OSS（读/搜索/Search-Around）、Actions Service（应用编辑）。Materialization 用于 schema 破坏性变更后迁移用户编辑。
- **硬限额**：String 属性 ≤ 12 MB；Array 属性 ≤ 100,000 元素；数组无 null 元素。
- （厂商口径：单对象类型数百亿对象、单次 action 编辑上限 ~10,000 对象——复刻时以我们实际事务能力为准。）

#### OSDK 代码生成

从本体元数据生成 TypeScript(NPM)/Python(Pip/Conda)/Java(Maven)/OpenAPI 绑定；token "scoped only to the ontological entities you want your application to access"。

```python
# Python OSDK 读（verbatim）
client.ontology.objects.ExampleRestaurant.get("primaryKey")
list(client.ontology.objects.ExampleRestaurant.iterate())
result = client.ontology.objects.ExampleRestaurant.page(page_size=30, page_token=None)
client.ontology.objects.ExampleRestaurant.where(
    ~ExampleRestaurant.object_type.restaurant_name.is_null()
).order_by(ExampleRestaurant.object_type.restaurant_name.asc()).iterate()
# & 为 AND, | 为 OR
client.ontology.objects.ExampleRestaurant.count().compute()
```

---

### 2.4 权限（Markings/角色/行列/写回）

**核心公式**：
> 读权限 = **(满足全部 Markings/Organizations 的强制门) AND (至少 Viewer 及以上 Role 的自主门) AND (通过对象/属性安全策略的行列过滤)**
> 写权限 = **一条完全独立的路径**（Action 的 apply 权限 + submission criteria），可让用户"改自己看不到的记录"

#### 一、两层地基：Mandatory AND Discretionary

- **Mandatory（强制）** = Markings + Organizations + Classifications。中央管理、否决式、沿血缘传播。原文："mandatory controls will always prevent an ineligible user from accessing a resource, regardless of the user's role"。
- **Discretionary（自主）** = Roles。**additive（只加不减）**——只能给用户加权限、不能减。

#### 二、Roles（自主层，RBAC）

4 个默认 Role，从强到弱：**Owner > Editor > Viewer > Discoverer**。
- 授权只能授**同级或更低**（Owner 可授 4 种；Discoverer 只能授 Discoverer）。
- 沿资源树继承（Project/folder 上的 Viewer 级联到内部全部资源）。
- 通常在 Project 级授权；可关闭 folder/file 级授权。
- 可自定义 Role。管 Role 需 Organization 上的 **"Manage roles and role sets"** 权限。
- 查看**对象类型**只需对本体资源有 View、不需对 backing datasource 有 View；查看**对象实例**须 View 对象类型 AND 有底层数据访问。

> **⚠ 更正 1（硬错误）**：旧本体 Role 是 **4 个**（Ontology Owner / Editor / Viewer / **Discoverer**），不是 3 个。（已被 Compass 项目 Role 取代。）

#### 三、Markings（强制层核心）

- 二元 **all-or-nothing**；标准 marking 之间**合取 boolean AND**（贴了 PII+FIN 必须两者都有资格）。
- 组织成 **Marking Category**。
- discovery restriction：无资格连资源存在都看不到。
- **沿两条链传播**：① 文件层级（Project/folder→内部资源级联）；② 数据依赖（每个依赖它的下游 Dataset 继承，称 **data marking**，取输入 marking 集合的**并集**）。
- saved 后立即应用、立即向下游传播。

> **⚠ 更正 2（机制归属）**：
> - **移除任一 marking = 一次 expand-access 事件**，由具名 **"Remove marking"** 权限门控（移除须同时具备 apply + remove 该 marking 的权限）。
> - 具名的 **"Expand access" 权限实际管的是 Organizations**（加/减组织）。
> - 二者不可混为一谈。
>
> **⚠ 更正 3**："Owner 改不动 marking" 偏强。默认 **Owner role 本身即赋予改 marking 的资源侧能力**（仍须叠加 marking 专属的 apply/remove 权限）。"解耦"成立在于 marking 专属权限中央管理、独立授予；但强制层"否决式、Owner 无法通过分享绕过"这一核心论断**完全属实**（原文："guaranteed to never be able to access that data, even if the project owner tries sharing it with them"）。

#### 四、CBAC（分类/多级安全，政府向）

- **默认关闭、需 Palantir 介入配置**。
- 结构：classification 组织成 category，可跨 category 组合。
- 关键差异：CBAC 的 category 支持**析取 disjunctive(OR)**（用户有该 category 中任一 marking 即可，用于 releasability 如 country A OR country B），而标准 marking 只有合取(AND)。
- 层级：Project 有 **maximum classification**（=allowed marking limit），更高分类的资源不能移入更低上限的 Project；用户按 clearance 层级访问（≤自身可见）。

#### 五、行/列/单元格级——两条实现路径

**路径 A｜Restricted View（RV，数据集层，老范式）**：叠在 backing dataset 上的过滤层，用 granular policy 按用户属性决定可见行。**RV 不能当 transform 输入**（防洗权限，安全边界必须是终点）；input 更新时后台自动重建。行级 marking 变体：表里加 STRING ARRAY 列存 marking ID。

**路径 B｜Object/Property Security Policy（本体层，新范式，推荐）**：
- **Object security policy** = 行级（对象实例是否可见）。
- **Property security policy** = 列级（只作用于选定属性，配置项同 object policy，但**不能含主键、每属性最多一条**）。
- **单元格级** = 两者组合——"user must pass both the object security policy and the property security policy to view the property value"。
- **失败语义**：不过 object policy → **整行不可见**；过 object 但不过 property → **该属性返回 null**。
- 默认继承 datasource 的全部 mandatory control，可增删。物化时取"最严"权限（合并所有源 marking + policy 加的 marking）。

#### 六、Granular Policy（判定内核——实装规格）

- **支持的用户属性（精确名）**：`User ID` / `Username` / `Group IDs` / `Group names` / `Authorized group IDs`(scoped session 用) / `Organization Marking IDs` / `Marking IDs` / IdP `Custom attributes`。
- **8 种比较算子**：`Equal` / `Less Than` / `Greater Than` / `Less-or-Equal` / `Greater-or-Equal`（**object security policy 不支持大小于类**）/ `Intersects`(至少一边集合) / `Subset of`(右边集合) / `Superset of`(左边集合)。
- **硬约束**：每策略**最多 10 个比较**；至少一项须与**用户属性**比较；引用 user/group/org **必须用 UUID**（不能用名字）；policy 列须非空（null 行不可访问）。
- **权重制**：常量-vs-字段 = 1；集合-vs-字段 = 1000；marking 条件 = 3000；单策略总权重上限 **<10000**；property policy 与 object policy 的 granular 权重合计须 <10000。

#### 七、行级 marking = Mandatory Control Property（精确 schema）

- base type = **Mandatory Control**；值 = **STRING ARRAY** of marking / organization ID。
- 配置步骤：① 建 marking-backed RV + marking 列 → ② Ontology Manager 把属性映射到该列 → ③ 属性设 base type = Mandatory Control → ④ 配 allowed values（allowed markings/organizations 或 CBAC max classification）→ ⑤ **设 required（强制不可空："mandatory control properties must be required"）** → ⑥ MDO 每 datasource 各配一个。
- 访问语义：markings + orgs 组合时 = 全部 marking AND 至少属一个 org；CBAC = 层级访问。

#### 八、Purpose-Based Access Control（PBAC）

- 访问权授予 **Purpose** 而非个人；用户申请加入某 Purpose（范围恰好够达成目标"no more, no less"）。
- 数据 owner 批准"某数据集可用于某 Purpose"时须记录 rationale；用户获批时治理团队也须记 rationale。
- 请求-审批-调用由 **Approvals 应用**统一管理。

#### 九、写回（Action）权限——独立于读的执行门

跑一个 Action 需三件事：
1. 能 view 被编辑的对象类型/link 类型/其 datasource；
2. 通过 submission criteria；
3. 满足对象类型的 writeback 设置。

**writeback 两模式**：
- **(a) "仅限 Action 编辑"（新对象类型默认，推荐）**：用户只需对被编辑对象有 **Read** 即可改（"users can modify records they cannot independently view"，即改自己看不全的记录）。
- **(b) 放开（Action+Forms+Object Explorer+API 都能编辑）**：须对 writeback dataset 有 **Edit**（会带来更宽的数据可见性，官方"discouraged"）。

Side effects/通知另需权限；收件人无权则跳过该收件人、Action 仍成功。

#### 十、Download/Export——第三根权限轴

- download **独立于 view**：Viewer/Editor/Owner 可下、**Discoverer 有 view 无 download**。
- Download category 支持 **checkpoint**（下载前须确认政策/填理由，使下载成为"intentional action"）。
- Cipher 加密使下载物仍为密文除非有解密权；`dataExport` 审计 category 记录每次下载。
- 官方声明有覆盖缺口："Not all download actions in Foundry are governed by roles"。

---

### 2.5 审计（audit.3 分类 + JSON schema）

以 **`audit.3`** schema 为核心的强制分类、append-only、隔离归档日志账本。三条骨架：**统一 envelope + 按业务动作分类（每条至少一个 category、多 category 并集）+ traceId 分布式串联**。

#### 顶层 envelope 字段

> **⚠ 更正（字段数）**：顶层 envelope **≥16 个字段**（不是"固定 12"）。`userAgent` / `users` / `entities` 是**顶层字段**，不是仅导出集才有。

| 字段 | 说明 |
|---|---|
| `time` | RFC3339Nano UTC，例 `2025-11-13T23:20:24.180Z` |
| `uid` | 用户 ID（if available），"最下游的调用者" |
| `orgId` | uid 所属组织 |
| `eventId` | 可审计事件唯一标识 |
| `logEntryId` | 这一行审计日志唯一标识 |
| `sequenceId` | （V3 额外字段） |
| `traceId` | "The Zipkin trace ID, if available"，跨服务串联键 |
| `categories` | 本事件命中的所有 audit category（数组，≥1） |
| `product` | 产生该日志的产品 |
| `name` | 事件标识，`(product)_(endpoint)` 格式 |
| `host` | 产生该日志的主机 |
| `userAgent` | 可查询列（顶层） |
| `users` | set&lt;ContextualizedUser&gt;，本条涉及全部用户（顶层，用于聚合） |
| `entities` | 本条 request/result 涉及的全部资源（顶层，用于聚合） |
| `requestFields` | 调用时刻入参（请求了什么） |
| `resultFields` | 方法执行派生信息（实际返回/命中了什么） |
| `result` | 成功/失败状态（含被拒绝的尝试）：`SUCCESS` / `ERROR` / `UNAUTHORIZED` … |

> **⚠ 更正（name 格式，硬错误）**：`name` 是 **全大写 + 下划线（SCREAMING_SNAKE_CASE）**，不是普通小写 snake_case。官方原文："generally following a (product name)_(endpoint name) structure in **ALL CAPS**, snake-cased"，示例 `DATA_PROXY_SERVICE_GENERATED_GET_DATASET_AS_CSV2`。下面示例已按此更正。
>
> **⚠ 更正（resource_id 存疑）**：`resource_id` 未在官方文档证实为标准导出列；社区实测导出 schema 未见此列。**勿作为可依赖列名写进实现**。
>
> **⚠ 更正（版本命名）**：`audit.3` 用 `requestFields`/`resultFields`；`audit.2` 用 `request_params`/`result_params`。audit.2↔audit.3 同名字段内容可能不同。

#### Category 全景（>100 个；按业务动作，节选并附必填字段）

| category | request 字段 | result 字段 |
|---|---|---|
| `dataLoad`（读取） | | `loadedResources`(req) |
| `dataExport`（导出/下载，最高危） | | `downloadedResources`(req)、`downloadedSize`(req, 字节) |
| `dataImport` | | `importedFilename`、`importResourceId`、`importedFileType` |
| `dataCreate` / `dataDelete` / `dataTransform` / `dataMerge` / `dataSearch` / `bulkDataImport` | `dataSearchQuery`(search) | `createdResources` / `deletedResources` / `transformTargets` / `mergedResult` / `dataSearchResults` |
| `authenticationCheck` | | `authenticationCheckResult` |
| `authorizationCheck`（含失败） | `authorizationCheckTargets`(opt)、`authorizationCheckOperations`(**req**) | `authorizationCheckSucceededTargets`(req)、`authorizationCheckFailedTargets`(req)、`authorizationCheckResultMessage`(opt) |
| `managementPermissions` | | `resourcesWithPermissionsChanges`(req)、`permissionChangeContext`(opt) |
| `managementGroups` / `managementUsers` / `managementMarkings` / `managementTokens` | | `groupPatches` / `managedUserIds` / `managedTokens` |
| `userLogin` / `userLogout` / `oauth2InitiateAuthFlow` | | `loginUserId`(opt) |
| `tokenGeneration` / `tokenAccess` / `tokenRevoke` | | |
| `logicCreate/Delete/Update/Access/Search` | | |
| `llmInference`（prompt 执行+生成） | `llmInferenceContext`(req)、`llmInferenceInputs`(req) | `llmInferenceResponses`(req)、`llmInferenceResponseContext`(req) |
| `llmRoute` | | |
| `metaDataAccess/Create/Delete/Update/Search` | | |
| `monitorCreate/…/Run/Search`、`requestCreate/Approve/Disapprove/Execute/Cancel/Update` | | |
| `dataShare` / `dataShareCreate` / `dataShareDisable` / `auditDataShareCreate`(签名 URL) | | |
| `appConfigAccess/Create/Delete/Update` | | |
| `userJustify`（用户目的说明，"why"的正式载体） | `userJustification`(**req**) | |
| `auditDataRedact`（泄露 remediation 脱敏） / `internal`(低信号兜底) / `passThrough`(运行时定参) | | |

#### 一条真实 audit.3 日志（多 category 并集）

```json
{
  "time": "2025-11-13T23:20:24.180Z",
  "uid": "8f3c1e42-....-user-uuid",
  "orgId": "ri.multipass..organization.9a2b-....",
  "eventId": "ri.audit..event.2f1c-....",
  "logEntryId": "ri.audit..logentry.7d4e-....",
  "sequenceId": "ri.audit..seq.e3f-....",
  "traceId": "e457b5a2e4d86bd1",
  "host": "foundry-catalog-7c9f-prod",
  "product": "foundry-catalog",
  "name": "CATALOG_GET_DATASET_ROWS",
  "categories": ["authorizationCheck", "dataLoad", "userJustify"],
  "result": "SUCCESS",
  "userAgent": "Mozilla/5.0 ...",
  "users": ["8f3c1e42-....-user-uuid"],
  "entities": ["ri.foundry.main.dataset.customers-pii"],
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

被拒绝场景（同一 traceId 另有一条，`result=UNAUTHORIZED`，**operations 是 required 必须带**）：

```json
{
  "time": "2025-11-13T23:20:24.050Z",
  "uid": "8f3c1e42-....-user-uuid",
  "traceId": "e457b5a2e4d86bd1",
  "categories": ["authorizationCheck"],
  "result": "UNAUTHORIZED",
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

#### Trace 生成与跨服务传播

- `traceId` = Zipkin trace ID（64-bit / 16 hex 或 128-bit / 32 hex）。由 `palantir/tracing-java`：client 注入 `X-B3-TraceId` header，Jetty server 端继续传播进后续 client 调用。
- Palantir 增强：额外发 `X-OrigSpanId`，使未采样（unsampled）请求日志也能作为 trace 事件的有用子集。
- Span 不可变；`CloseableTracer`（单线程）/ `DetachedSpan`（跨线程）管理生命周期。
- AIP 侧另有 `foundryTraceId`；service log tags 里 `x-b3-traceid` 是 best-effort（Ontology SDK 等外部来源可能缺失）。

#### 存储 / 交付 / 合规

- **Append-only**：原文（在 monitor-audit-logs 页）："The infrastructure through which audit logs flow from generation to storage is engineered to be append-only, ensuring audit trail integrity."
- **隔离归档**："Access to log archival storage is aggressively restricted."（删除须与 Palantir Support 制定 remediation plan）。
- **交付两路**：① API 轮询——`list-log-files` + `get-log-file-content`（audit-v2，路径 `/api/v2/audit/organizations/{orgId}/logFiles(/{logFileId}/content)`，需 `api:audit-read` scope），SIEM 直连不经 Foundry；② 导出到 per-organization Foundry 数据集。
- **延迟**：audit.3 目标 ≤~15min（最优数分钟），相对 audit.2 的 24h+。
- **性能约束**：查询/聚合前**先按 `time` 列过滤**（官方逐字要求）。

---

### 2.6 血缘（节点/边 + 列级 + 安全传播）

两根轴，实装时必须分开对待：**(A) 图血缘（数据集级 node-level）** + **(B) 列/单元级安全（Marking 传播）**。

> **关键澄清**：Foundry 的血缘图**本身是数据集级，不是列到列（column-to-column）的字段推导图**。官方所谓 "column-level" 指两件事：① Data Lineage 里的**列检索**（Frequent Columns，判断"哪些数据集含某列"=列的**存在性**）；② **property/cell-level security marking**（沿血缘继承）。真正随血缘传播的是 **Marking**，不是列推导血缘。

#### A. 图血缘

**节点类型**：Dataset、Transform(=job spec)、Schedule、Artifact、Ontology 实体、Source/Sync。**边**：有向"数据依赖"（上游→下游）。

**自动生成**：因 sync 产物与 transform 的输入/输出**都是同一个 Dataset 抽象**，每次 build 时框架天然知道上下游，累积即端到端图。`@transform` + `Input()`/`Output()` 声明就是登记依赖。

**图交互（Data Lineage app）**：Expand（chevron 选层数 / double-chevron 到 raw 源）、Find（按名 + 列名）、Drag select、Histogram of selection properties → **Frequent Columns**（勾列高亮含该列的资源）、Save/Open/只读分享链接、Branching data lineage。节点详情 tab：logs / files / metadata / schema / job specifications。

**Node coloring 枚举**：

> **⚠ 更正（枚举不完整）**：是 **6 种**，不是 5 种。补 **`Resource overview`**（默认模式，按资源类型着色，legend 区分 Dataset/Artifact/Writeback Dataset）。

| 模式 | 说明 |
|---|---|
| `Resource overview` | **默认**，按资源类型着色 |
| `Build Status` | running 的数据集有 open transaction |
| `Build Duration` | 各数据集构建耗时 |
| `Out-of-date`(Staleness) | 哪些 job spec 被判 stale |
| `Permissions` | 用户对各资源的可见权限 |
| `Marking Changes` | **仅 simulation mode** 生效 |

**Build/回滚**：图上直接 Build datasets、Manage schedules、Roll back a pipeline / dataset。

#### B. 安全随血缘传播（核心）

- **Marking = 强制控制**：二元 all-or-nothing、多 marking 合取 AND、**Markings travel with the data**（跟数据走）。
- **两条继承路径**：① 文件层级（Project/文件夹→内部一切继承）；② 直接数据依赖（依赖它的每个下游继承，称 **data marking**，"propagate through transform and analysis logic"，saved 后立即传播）。

**摘除传播（transform 属性，Python API）**：

> **⚠ 更正（会踩坑）**：`Markings` / `OrgMarkings` 是**两个必填位置参数** `(marking_ids, on_branches)`，第二个是"应用摘除的受保护分支列表"。只传一个 list 会报错/不生效。

```python
from transforms.api import transform, Input, Output, Markings, OrgMarkings
@transform(
    out=Output("/mfg/clean/workshop_cost"),
    salary=Input("/mfg/raw/worker_salary",
                 stop_propagating=Markings(["<marking_id>"], ["<protected_branch>"]),  # 摘 PII
                 stop_requiring=OrgMarkings(["<org_id>"], ["<protected_branch>"])),     # 摘 Org
)
def compute(salary): ...
# 生效前提：分支受保护 + "Require security approvals before merging" 开启；
# 且无法摘除某继承 Marking，直到你的分支被合并进受保护分支。
```
> Organization 是特殊 Marking（故关键字 `OrgMarkings`；Create Marking API 中 Org 类 `categoryId` 为字面 `"Organization"`）。

**列/单元级安全（真正的 column-level）**：见 [2.4 路径 B]。Mandatory control property（OSv2）：base type = Mandatory Control，映射 RV marking 列，配 Allowed markings / Allowed organizations / Max classification。

> **⚠ 更正（CBAC 措辞收窄）**：CBAC 可与普通 marking 在同一资源上并存（取 AND）。"分类不能与 marking/organization 同挂一属性"应弱化为"分类作为独立 mandatory control 维度配置；**同一 mandatory control property 承载单一控制类型**"。

**Restricted View**：行/列级只读视图；**故意不可作 transform 输入**（逐字属实）；"不可导出/sync"是合理推论（唯有 materialize——需较高权限、物化后不带 RV policy——才能转常规 dataset 供下游/导出）。物化对象数据携带 Dataset + 对象类型双来源 provenance。

#### C. 三大用途 + Marking 变更模拟

- **影响分析**（正向）：改上游影响哪些下游 App/对象/报表。
- **调试**（反向）：异常由哪个上游节点/哪次 build 引入。
- **合规/provenance**：完整来源链。
- **Marking 变更模拟（独有）**：toggle "Simulate access requirements" → 选数据集 → Edit markings → "Simulate changes"。图着色 4 状态：`Simulate changes applied`（你改的节点）/ `Access affected`（改前后不同）/ `Access unaffected` / `No visible transactions`（未构建过/无权看事务）。**限制**：依赖最近一次 build；通过 lineage 或父 Project 继承而来的 Marking 之移除无法被模拟。

**Create Marking API（admin v2）请求体**：

| 字段 | 类型 | 必填 |
|---|---|---|
| `name` | string | 是 |
| `description` | string | 否 |
| `categoryId` | string(UUID；Org 类为字面 "Organization") | 是 |
| `initialMembers` | list&lt;PrincipalId&gt; | 否 |
| `initialRoleAssignments` | list&lt;MarkingRoleUpdate&gt;(至少 1 个 ADMINISTER) | 否 |

响应：`id`、`categoryId`、`name`、`description`、`organization`(RID)、`createdTime`(ISO8601)、`createdBy`。Remove Markings 端点需资源 RID + OAuth scope `api:filesystem-write`。

---

### 2.7 数据健康（监控目录：信号/阈值/告警）

三个协作机制：**(A) Health Checks（资源级细粒度）+ (B) Monitoring Views（运行面规模化）+ 构建期门禁 Data Expectations（见 2.2）**。

**通用参数**：`Severity`（枚举 **Moderate | Critical**）、`Escalate`（连续失败 N 次升级 critical）、`Notes`、`Issues`（失败自动开 issue、恢复自动关）。阈值操作符：**Between | ≥ | ≤ | =**。多数数值检查支持 **Median deviation**（异常带）。

#### A. Health Checks 完整目录（5 类）

**A1. Status 类**：
- `Job Status`（该 dataset 最近一次 job 成功）、`Build Status`（最近一次 build 成功）、`Schedule Status`（最近一次 schedule build 含所有中间产物成功）、`Sync Status`（参数 `Sync destination` 必填）。

**A2. Time 类**：
- `Build Duration`、`Sync Duration`（含 Median deviation）。
- `Time Since Last Updated (TSLU)` = 当前时间 − 最近事务提交时间；参数 `Last updated`+操作符、`Ignore empty transactions`(Y/N 必填)、`Schedule`(**Automatic | Custom Schedule** 必填)、Median deviation。
- `Time Since Sync Last Updated`。
- `Data Freshness` = 最近事务提交时间 − 某时间戳列最大值；参数 `Column name`(必填)+`Freshness range`+操作符。
- `Sync Freshness`。

**A3. Size 类**：
- `Row Count`(+MAD)、`Dataset File Count` / `Transaction File Count`、`Transaction File Size`。
- `Dataset Partition`（无配置）：<50 文件即 pass；≥50 文件时需 ≥90% 文件 >96MB 才 pass（小文件治理）。

**A4. Content 类**：
- `Primary Key`（100% 唯一且非空，参数仅 `Column name`）、`Null Percentage`、`Allowed Column Values`、`Numeric Range`（格式 `min-max`）、`Numeric Mean` / `Numeric Median`、`Approximate Unique Percentage`、`Column Regex`、`Date Range`（格式 `YYYY-MM-DD – YYYY-MM-DD`）、`Approximate Column Relation`（跨数据集列相似度：`Other dataset path`+`Column1`+`Column2`+`% match`，≈外键/对账）。

**A5. Schema 类**：
- `Column`（`Column name`+`Is Present`+`Type`）、`Column Count`、`Schema`（`Comparison type` 四枚举）：
  - `EXACT_MATCH_ORDERED_COLUMNS`（列序+名+类型+数全一致）
  - `EXACT_MATCH_UNORDERED_COLUMNS`（忽略序）
  - `COLUMN_ADDITIONS_ALLOWED`（可新增列，既有列必须在）
  - `COLUMN_ADDITIONS_ALLOWED_STRICT`（新增后既有列锁定）

#### B. Monitoring Rules 目录（运行面，alert severity 枚举 **Low | Medium | High**）

| 面 | rule | 默认阈值/严重级 |
|---|---|---|
| Schedule | `Consecutive schedule failures`(排除 cancelled) | ≥1 medium，≥3 high |
| Schedule | `Schedule duration` | ≥2h |
| Dataset | `Time since job last succeeded` | >1 day |
| Stream(derived) | `Total lag` | >1000 |
| Stream(derived) | `Liveness: time since last checkpoint` | ≥2min |
| Stream(derived) | `Last checkpoint duration` / `Total throughput` | >10min / <100 |
| Stream(ingest) | `Records ingested over last 5/30min/1h/4h/1d` | ≤100 |
| Object/Link | `Sync jobs failing` | ≥1 low / ≥3 medium / ≥7 high |
| Object/Link | `Invalid stream records detected` | 不可配，≥1 即 **Critical** |
| Object/Link | `Sync propagation delay` | ≥1day |
| Function/Action | `... duration p95` / `Number of ... failures`(窗口 1h) | >10s / >0 |
| Live deployment | `heartbeat` | ≥1min |
| Agent | `High CPU` / `JVM heap` / `Low disk` / `Queue size` | >80% / >70% / <10GB / >70 jobs |
| Agent | 证书到期 / 心跳陈旧 | <30d medium <10d high / >10min |
| Automation | `disabled by the system` / `repeated failures`(窗口 1h) | 不可配 High / >0 |

#### 异常带（Median deviation / MAD）

不用真标准差（对 build 离群值敏感），用 **Median Absolute Deviation**：`σ ≈ MAD × 1.4826`（MAD = 数据到中位数绝对偏差的中位数）。配置 = "允许偏离几个标准差" + "采样最近多少个 build 作基线"，实现自适应基线告警。

#### 评估触发 + 告警 + issue

- **评估模式**：`Automatic`（dataset 更新时 / 到时间阈值时触发）或 `Custom Schedule`（固定 minute/hourly/daily/weekly/cron）。
- **watch/订阅级别**：`Nothing` | `All failures`(Moderate+Critical) | `Only critical`。
- **渠道**：站内通知**永远**发给失败检查的 watcher；邮件 opt-in；**PagerDuty / Slack / Webhook(REST)** 在 monitoring view 级配置（severity 门限、snooze）。
- **issue**：勾选"失败时自动创建 issue"（可指定 assignee，恢复后自动关闭）。
- **escalate**："Add time"，连续失败时长/次数后升级 critical。

#### 一个"生产数据集监控页"应显示的 KPI

| 分区 | KPI | 形态 |
|---|---|---|
| 概览 | 聚合健康状态 | Healthy / Failing(有 Critical) / Warning(仅 Moderate)，取最严 |
| 概览 | Last build / job status | Succeeded / Failed + 时间戳 |
| 概览 | Freshness | TSLU 值 vs 阈值 |
| 概览 | Row count | 当前值 + 与基线偏差(MAD σ 数) |
| 检查清单 | 每检查一行 | 检查名·类别·状态·严重级·阈值·实测值·上次评估时间·watch |
| 历史 | 检查历史 | 时间轴 pass/fail + 实测值 + 触发的 build/transaction id |
| 告警 | 未关闭 issue | 标题·assignee·开启时间·关联失败检查 |
| 血缘 | 上游健康 | 直接上游 dataset 健康状态（红/黄/绿），反向溯源 |

---

### 2.8 报表 & Control Panel（字段级清单）

三块：**(A) Workshop 操作应用 widget + (B) Object Explorer 探索 + (C) 管理者 Control Panel**。铁律：**读走对象、写走 Action、每步留痕**。

#### A. Workshop widget（4 大类 + 3 补充类）

绑定机制：每个 widget 有 input/output variables；某 widget 改变量 → 依赖该变量的所有 widget 响应式重渲染。

<details><summary>widget 全目录</summary>

1. **Core display**：Object Table、Object List、Object View、Property List、Links、Object Set Title。
2. **Visualization**：Chart XY、Vega Chart、Map、Gantt Chart、Pie Chart、Stepper、Markdown、Metric Card、Pivot Table、Timeline、Resource List、Media Preview、Spreadsheet Display、PDF Viewer、Image Annotation、Free-form Analysis、Time Series Analysis、Data Freshness、Edit History、Linked Compass Resources、Action Log Timeline。
3. **Filtering**：Filter List、Object Dropdown、Object Selector、String Selector、Date and Time Picker、Text Input、Numeric Input、Exploration Filter Pills、Exploration Search Bar、Prominent Term、User Select。
4. **Event/navigational**：Button Group、Media Uploader、Comments、Tabs、Inline Action、Audio Recorder。
5. **AIP**：AIP Analyst / AIP Chatbot / AIP Generated Content。

</details>

**Object Table（最能代表操作应用）**：
- 输入：Object set。输出：Active object / Selected objects / 右键对象。
- 列类型：标准属性、Linked object properties、Time series（transform+summarizer+sparkline）、**Function-backed columns**（入 ObjectSet&lt;T&gt;，出 Map/Record/dict）、URL link、Struct/Custom/Array、多对象类型同表或分 tab。
- 表级开关（确切名）：Number of lines to display per row、Enable value wrapping、Number of frozen columns、Fit columns horizontally、Enable narrow headers(50→30px)、Show security markings、Default sort(s)、Enable multi-select、Disable active object auto-selection、Hide column configuration、Empty state message、Variable-backed column visibility。
- **导出上限**：CSV **≤10,000 行**；Excel **≤200,000 行**。
- **行内编辑暂存**：非 function-backed **≤200 行**；function-backed **≤20 行**（须 ontology 里有 Modify object 规则的 action，参数为原生类型且 from parameter）。

**Filter List**：输入 Object set，输出 object set filter 变量。组件：Keyword(AND/OR/NOT+括号) / Histogram / Single-select / Multi-select / Distribution chart / Single date / Multi-date / Timeline。布局 vertical scroll | horizontal pills。

**Metric Card**：Primary/Secondary metric(String|Number)、Label、Description、Sparkline(time range: All time|Last hour|Last day|Last week|custom)、Layout Card|Tag|List、size Compact|Regular|Large、Conditional formatting 阈值、Interactive metric（点卡片触发 command/action/event）。

#### B. Object Explorer（探索起点）

图表类型（= 某属性的聚合）：
- `Listogram`（非数值属性）、`Pie Chart`（布尔/字符串）、`Histogram`（数值/日期，自动分桶）、`Grid Plot`（二维色块 X+GroupBy）、`Single Statistic`（**不能用于筛选**）、`Statistics Table`（分组聚合表）、`Cluster Map`（geopoint）、`Choropleth Map`（typeclass: countries|us_states|us_counties|us_zip_codes）。
- 聚合选项：`Sum` / `Average` / `Min` / `Max` / `Count` / `Unique Count`。

右上三类按钮：`Actions`（对当前/选中对象写回，**选中 >1000 对象时不可用**）、`Open In`（带到其他应用）、`Export`（导出/复制 object IDs / Excel）。

#### C. 管理者 Control Panel

权限两级：**Enrollment（企业级）** 与 **Organization（组织级）**，各有独立管理页（Cmd/Ctrl+J 全局搜索）。

**C1. 安全 & 访问**：Authentication（SAML/OIDC/MFA）、Users/Groups、Roles、Organizations & Spaces、Networking & Egress。

**Roles（角色 = 一组 operations）**：默认 Owner / Editor / Viewer / Discoverer（上下文角色如 Ontology Owner/Editor）。operation 示例 `stemma:mutate-default-branch`(Change default branch)、`stemma:mutate-branch`。自定义角色：Platform/Foundry Settings → Roles → New Role → 命名 → 可继承已有角色 + 勾选 operations。管 Role 需 Organization 的 "Manage roles and role sets"（授权在 Control Panel → Organization Administrator；实际管理在 Foundry/Platform Settings → Roles，两处分述）。

**C2. Resource Management**（需 Resource management 应用访问权）：
- **Usage types（4 类计量）**：`Foundry Compute`（compute-seconds；batch/interactive/continuous）、`Query Compute-Seconds`、`Ontology Volume`（GB-months）、`Foundry Storage`（GB-months）。
- **Budgets 字段**：`Scope`(All usage / Usage account)、`Frequency`(Monthly/Quarterly/Yearly/Non-recurring)、`Budgeted amount`、`Start date`（非周期需 end date）、`Description`、`Notification thresholds`(%)、`Users to notify`。**仅追踪+告警，无硬阻断**；通知有延迟（可达 26h）。
- **Monitors**（绑 budget，接近预算时通知）、**Resource Queues**（FIFO 申请 vCPU/vGPU，守护 Job/Continuous/Session compute）。

**C3. 用户活动 & 审计**：`Analyze user activity metrics` 页；Audit（audit.3，见 2.5）。

---

### 2.9 AIP-Action（agent 执行与治理化写回）

AIP 三条线 + 一个 copilot：**AIP Logic（无状态 LLM 函数）+ Agent Studio/Chatbot Studio（有状态对话）+ AIP Evals（离线回归）+ AIP Assist（内置 copilot）**。核心：把"检索结构化对象图 + 调受治理 Action 写回 + 全程权限即审计 + 离线 evals 回归"焊在 Ontology 语义层上。

#### AIP Logic

无状态"LLM 函数"。核心是 **Use LLM block** 三件套：**Prompt**（可引用入参 `{{salesOrder}}`）+ **Tools**（三类本体工具）+ **Output**（返回类型：primitive / ontology object / struct）。产物是带类型签名、可被 Workshop/Agent/API/另一 Logic 调用的生产函数。
**抑幻觉**：原文"restricting LLM access exclusively to authenticated Ontology data rather than relying on model training data"——LLM 只能访问认证过的本体数据，权限经 Ontology permissions + function-level security 收窄到最小集。

#### Agent Studio 检索注入（每条消息确定性执行）

三种 retrieval context，结果拼进 system prompt：
- **Ontology context**：对象集来源 = Static input（整个对象类型）或 Variable input（经 application state 过滤）；检索模式 = 固定 N 个 或 语义检索 top-K（需对象类型上有 vector embedding 属性）；可勾选哪些属性进 prompt（默认全选可打印属性，排除 media reference/vector 省 token）；产出 object set + citation 变量。
- **Document context**：整篇全文 或 语义检索 top-K chunks（chunks 模式 beta）。
- **Function-backed context**：TS 注解 `@AipAgentsContextRetrieval()`，唯一必填入参 `messages: MessageList`，返回 `retrievedPrompt: string`（"pasted into the LLM system prompt"）。

#### prompted vs native tool calling

- **Prompted**：工具说明写进 prompt，一次调一个、顺序执行；兼容全部模型 + 全部工具类型；较慢。
- **Native**：模型原生 function-calling，可并行、token 省；仅限一部分 Palantir 自家模型 + **4 类工具**（Actions / Object Query / Function / Update Application Variable）。不支持的退回 prompted。

**6+ 类 agent 工具**：Action（自动执行 或 需用户确认）、Object Query（过滤/聚合/inspection/沿 link 遍历）、Function（调 Foundry 函数含已发布 AIP Logic）、Update Application Variable、Command（触发其他应用）、Request Clarification（暂停反问）。部署后 chatbot 提供 **View reasoning**。

#### governed Action 安全写回（AI 动手的唯一窄门）

三环护栏（同 2.3 Action Type）：(a) Rules（11 类 ontology 规则）、(b) Submission criteria（提交条件）、(c) Permissions（三维度：谁能 view / edit / apply）。
**安全总纲**："all governance and security controls apply equally to AI agents and humans"——AI agent 与人走同一套权限，**agent 有效权限 ≤ 调用者**。

#### agent 端到端执行形态

```
用户自然语言
  → 每条消息触发确定性 retrieval（Ontology/Document/Function context）拼进 system prompt
  → LLM 经 prompted/native tool calling 选工具
  → Object Query 读对象图（沿 link 遍历、聚合）+ Function 算逻辑
  → LLM 决策；若需写：
      → 先对 Action 跑 Validate（POST .../actions/{actionType}/validate）
          返回 result: VALID|INVALID + submissionCriteria[] + 每参数 evaluatedConstraints
      → 通过则 Apply（POST .../actions/{actionType}/apply，body {"parameters":{...}}）
      → 边改边校验+权限+审计，落 Ontology 并留 lineage
  → 结果喂回 LLM 循环至终答
  → View reasoning 回放决策链
  → AIP Evals 离线对整条函数/agent 跑测试套件回归
```

#### REST API — Validate / Apply Action

```
# Validate（写前校验，agent 决策关键）
POST /api/v1/ontologies/{ontologyRid}/actions/{actionType}/validate   scope: api:ontologies-read
Response:
{
  "result": "VALID" | "INVALID",
  "submissionCriteria": [ { "configuredFailureMessage": "string", "result": "VALID"|"INVALID" } ],
  "parameters": {
    "<parameterId>": {
      "result": "VALID"|"INVALID", "required": <bool>,
      "evaluatedConstraints": [ { "type": "range"|"oneOf"|"arraySize"|"objectPropertyValue"|"objectQueryResult", ... } ]
    }
  }
}
# ⚠ "Validations will not consider existing objects or other data in Foundry"
#   —— validate 不查现有对象；"库存够不够"必须靠 Object Query 另行判断。

# Apply
POST /api/v1/ontologies/{ontologyRid}/actions/{actionType}/apply   scope: api:ontologies-read api:ontologies-write
Body: {"parameters": { "<ParameterId>": <DataValue>, ... }}
# options: returnEdits / validateOnly（二者互斥）；OSV1 最终一致、OSV2 立即可见；不支持参数默认值（未传即 null）
```

```typescript
// OSDK 写回（TypeScript）
const result = await client(addReview).applyAction(
  { restaurantId:"...", reviewRating:5, reviewSummary:"It was great!" },
  { $returnEdits: true }   // 或 $validateOnly: true（二者不可同时）
);
if (result.type === "edits") { /* 成功 */ } else { /* validation failed */ }
```

#### AIP Evals

- **graders 三类**：
  - 确定性：Exact boolean/string/numeric/array match、Regex match、Levenshtein distance、String length、Keyword checker、Exact object match、Object set contains/size range、Integer/Floating-point/Temporal range、ROUGE score 等。
  - LLM-backed：`LLM-as-a-judge`（自定义条件返 bool）、`Rubric grader`（动态量规打分）、`Contains key details`（校验关键事实齐全）。
  - 自定义：已发布 Foundry 函数或 AIP Logic（须至少返回一个 Boolean 或 numeric，可返 struct 多指标）。
- **测试用例**：Input columns → Expected/Actual value 映射到 evaluator。
- **Objectives/阈值**：bool 指标指定应为 true/false；maximize 指标设最小阈（≥X）；minimize 设最大阈（≤X）；单指标达标即 pass，一次迭代内全指标达标该迭代才 pass。
- **多次聚合**：官方建议每用例跑 **≥3 次**再聚合（"running test cases at least three times for LLM-backed functions is recommended"）；结果表支持 Group by。

---

## 3. 我们栈上的落地映射与取舍

> 栈：StarRocks / PostgreSQL / Flink CDC / Neo4j / pgvector / 只读 MCP + JSONL 审计 / 无头 Claude / Streamlit。现有落点见括号文件。**当前全只读，最大缺口 = governed Action 写回 + Markings 沿血缘传播。**

### 3.1 连接器 → Source 对象化

| Palantir | 我们复刻 | 现状/落点 |
|---|---|---|
| **Source 对象** | **抽出一个 Source 配置对象（YAML/表）**：`{source_id, type(postgres/rest/file), host, port, credentials_ref, network_policy, markings[], tables[], cursor_col, initial_value}`，把"哪些表/游标列/凭证/密级"从 SQL 解耦 | **当前最大缺口**：连接元数据硬编码在 `pipeline/gen_flink_cdc_sql.py`（`host='dm-postgres'`、`slot.name=flink_<t>`） |
| Streaming/Incremental sync | 已有 Flink CDC（postgres-cdc）：WAL 的 **LSN = 高水位游标**；`scan.incremental.snapshot.enabled=true` = 官方"全量→增量"开关。补显式 APPEND vs SNAPSHOT 标注（StarRocks 主键模型=SNAPSHOT/UPSERT，明细模型=APPEND） | 已有 `gen_flink_cdc_sql.py` |
| Batch/JDBC 增量 | 对未上 CDC 的源（U8/ERP）照 Palantir 写参数化 SQL `WHERE updated_at > :cursor`，游标持久化到 `sync_state`(source_id, table, last_cursor, last_run_ts) 表，失败可恢复 | 新增 |
| 事务原子性 | StarRocks Stream Load 的 label 幂等 + 事务，失败不 commit；或先落 staging 表原子 swap，不留半截脏数据 | 新增护栏 |
| 凭证保管 | 凭证存加密（SOPS/age 或 PG pgcrypto），运行时解密、不落日志；MCP 审计绝不记凭证 | 现凭证在 compose env/明文，需改 |
| **Virtual table** | **StarRocks External Catalog（JDBC/Iceberg/Hive）= virtual table + pushdown 天然对应**，不落地直查 PG/Iceberg、谓词下推。低成本高价值 | 新增，推荐早做 |

### 3.2 转换/分层 → dbt on StarRocks（替代命令式 dm-load）

| Palantir | 我们复刻 | 取舍 |
|---|---|---|
| `@transform` + `Input()` 自动 DAG | **dbt `ref('upstream')`**——声明依赖、框架拼 DAG、拓扑排序、只重算受影响下游。一个 dbt model .sql = 一个 `@transform_df`。有官方 `dbt-starrocks` adapter | 把 `warehouse/load.py` 的 19 表命令式建表迁到 dbt models |
| 三段式项目 | `models/staging`(raw→clean，一源一 `stg_`，显式 CAST) → `models/marts`(canonical) → `models/ontology`(对象表，喂 Neo4j/MCP) | 补上"源端漂移无落库前拦截"缺口 |
| `@incremental` | dbt `{{ config(materialized='incremental', unique_key='...') }}` + `is_incremental()`(=`ctx.is_incremental`) + `WHERE updated_at > (SELECT max(updated_at) FROM {{ this }})`(=`dataframe('added')`)。append/merge/insert_overwrite 分别 = APPEND/UPDATE/SNAPSHOT-of-partition | Flink CDC 负责源→raw 增量，dbt 负责 raw→clean→canonical 增量 |
| 事务/分支 | StarRocks 按日期分区（近似 SNAPSHOT-per-partition + insert_overwrite 单分区重跑）；需真时间旅行/分支时给落库表上 Apache Iceberg | 是否引入 Iceberg 待决策（运维成本 vs 实验分支需求） |
| Data Expectations 门禁 | dbt schema tests（not_null/unique/accepted_values/relationships）+ dbt-expectations（值域/行数）= `Check(on_error='FAIL')`；`dbt source freshness` = Freshness 检查；失败复用 `dm-dingtalk push` | 把 `pipeline/health.py` 的 `cdc_reconcile()` 升级为构建期 abort 门禁 |
| 事件调度 | Dagster sensor 监听 Flink CDC 落库（新分区/新事务）触发下游 dbt 资产 = event trigger + AND/OR 复合 | 新增（可选） |
| 血缘 | dbt manifest.json + dbt docs 血缘图；接 OpenLineage → Marquez/Neo4j | 见 3.6 |

### 3.3 Ontology → 对象类型注册表 + Neo4j + 写回 Action

| 构件 | 我们复刻 | 落点 |
|---|---|---|
| Object Type | 把 `schema.py` 19 表升级为**对象类型注册表**（YAML/JSON SSOT）：显式声明 `api_name`(PascalCase)、`display_name`、`primary_key`、`title_property`、`backing_datasource`、`status`、`groups`、`aliases`。落实"1 datasource ↔ 1 object type"（每对象类型绑一张 StarRocks 视图）。**强制主键确定性**（用业务 ID M0001/SO0001/S001 而非行号） | `schema.py` 已是 SSOT，扩元数据 |
| Property + Value Type | 每列扩 `base_type`(映射 String/Integer/Double/Date/Timestamp/Struct/Geoshape…)、`description`、`unit`、`visibility`、`searchable/sortable`、`value_type` 约束(Range/Regex/Enum/UUID)。**Vector 属性天然对应 pgvector 列**（物料/文档嵌入声明为对象 vector 属性） | pgvector 已有 |
| Link Type | n-1/1-1 → StarRocks 外键约定；m-n → join 表（如 material_supplier）；**物化进 Neo4j**（节点=对象、边=link type），天然支持 Search-Around | Neo4j 已搭好（S3） |
| **Action + 写回** | **当前最大缺口**。定义 action 注册表（parameters + rules + submission_criteria + side_effects + permissions）。最小可行 Action = `shipOrder`：submission_criteria 用 `is greater than or equals` 实现"stock ≥ demand"；rules = Modify object(库存-) + Create link(order→shipment)；**写回落 PostgreSQL 源**（OLTP 事务强），由 Flink CDC 传导回 StarRocks 形成闭环；side_effect = 钉钉推送(≈Notification)；全程 JSONL 审计 | 新增独立写通道，**不走只读 MCP** |
| Function | 把散在各处的业务逻辑（可发量计算、缺料判断）抽成 Python 函数层，既供 MCP 也供 action 驱动（≈function-backed action） | 新增 |
| OSDK 类比 | 从对象注册表**生成 MCP 工具 schema**（现有 3 只读 → 加带 submission_criteria 校验的写工具）；token/权限按对象类型范围化 | 扩 `connector/mcp_server.py` |

### 3.4 权限 → 策略即数据（PG 元表）+ MCP 三道门

**策略元表放 PG**（要频繁读写、事务性；不放 StarRocks 只读仓）：
```
markings(marking_id UUID PK, name, category_id, kind ENUM['standard','cbac','org'], is_disjunctive BOOL)
user_markings(user_id, marking_id)
resource_markings(resource_type, resource_id, marking_id)
roles(role_id, name, rank INT)  -- 固定 4 行 Owner/Editor/Viewer/Discoverer
role_grants(subject_id, resource_id, role_id)  -- 沿资源树继承(物化路径/递归 CTE)
granular_policies(policy_id, target_type ENUM['object','property'], target_id, expr JSONB)
  -- expr: rules 数组 {left:user_attr, op:ENUM(8种), right:{col|const}} + 逻辑树 All/Any/None
  -- 强制校验：≤10 比较、≥1 项比用户属性、权重<10000
purposes / purpose_datasets / purpose_users  -- PBAC 事前审批；session_id 升级为 purpose 句柄
```

**强制层在只读 MCP 实装（唯一读入口 = 安全边界终点，等价 RV 不可作 transform 输入）**，返回前三道过滤（用 mcp-config 注入的 `user_id` + `purpose_id`）：
1. **强制门(Markings)**：`resource_markings ∩ user_markings`，标准 marking 要求 `user_markings ⊇ 资源全部标准 marking`(AND)，CBAC category 内 OR；不满足 → 整表拒绝 + 写 `authorizationCheck` 审计(denied)。
2. **自主门(Role)**：`role_grants` Viewer+ 放行读、Discoverer 禁 download（= 禁导出/落文件）。
3. **行/列/单元格**：行级 → 用 caller 身份重写 SQL 注入 WHERE（marking-backed：`WHERE row_markings <@ user_marking_array` PG 数组算子；或属性匹配）；列级 → 按 property policy 把无权列在返回 JSON 里**置 null**（不是报错），并加 `_redacted` 标记让 Claude 理解 null 是"无权"而非"数据缺失"。行级 marking 列：StarRocks 敏感表加 `ARRAY<STRING>` 列存该行 marking ID（对应 mandatory control property，建模置 NOT NULL 复刻 required），CDC 从 PG 带过来。

**写回 Action 独立执行门**：`action_types(action_id, target_table, submission_criteria JSONB)`；校验 = 能 view 目标对象 AND 过 submission criteria AND writeback 模式；"仅-Action"模式只查 Read 不查行级可见（复刻"改看不到的记录"）。

### 3.5 审计 → JSONL 升级为 audit.3 envelope

（改 `connector/` + 新建 `dm/audit.py`，用 Pydantic 定义 `AuditLogEntry` + 每 category fields 作 SSOT）

| Palantir | 我们复刻 |
|---|---|
| envelope | 每行一个 audit.3 对象：`time`(RFC3339Nano UTC)、`uid`、`orgId`(固定"dm")、`eventId`(uuid4)、`logEntryId`(uuid4)、`traceId`(见下)、`host`、`product`("dm-mcp"/"dm-agent")、`name`(**大写** `MCP_RUN_SQL`)、`categories`、`result`(SUCCESS/ERROR/UNAUTHORIZED)、`requestFields`、`resultFields`、`entities`、`users` |
| category 裁剪(>100→6-8) | MCP：`dataLoad`(run_sql→`loadedResources`)、`dataSearch`(RAG/pgvector)、`authorizationCheck`(含失败)、`userJustify`(session 目的)；agent：`llmInference`(记脱敏 prompt 摘要+答案摘要)；治理：`managementPermissions`/`managementMarkings`；导出：`dataExport`(→`downloadedSize`)。字段名直接照抄官方 |
| **traceId 跨调用传播** | `session_id` 继续做 purpose 句柄；**另加 per-request `trace_id`**：`claude -p` 每步生成 16 位 hex，经 mcp-config env(`DM_TRACE_ID`)注入 MCP 子进程；MCP 再调 StarRocks/PG/Neo4j/pgvector 时把同一 trace_id 落各自 JSONL。session_id=purpose(一次会话)，trace_id=一次操作(会话内一步) |
| authorizationCheck | MCP 返回前做鉴权判定，**放行或拒绝都写一条**；被拒绝 `result=UNAUTHORIZED` + `authorizationCheckFailedTargets` + message。**被拒绝必须记**（合规首查项） |
| append-only + 隔离归档 | "JSONL 追加 + 只读分离"已对；上生产把 `logs/*.jsonl` 定期 append 进 StarRocks/PG 只追加审计表，归档目录设为写入进程外只读（OS 权限 + WORM/版本化） |
| eval | 新增审计 eval：① 每次工具调用后断言 JSONL 出现合法 audit.3 行；② 一次多步会话所有日志 trace_id 相同；③ 被拒绝必产生 `result=UNAUTHORIZED` + message；④ dataExport 必带 downloadedSize |

### 3.6 血缘 → Neo4j（天然载体，最大杠杆）

| Palantir | 我们复刻 | 落点 |
|---|---|---|
| 图血缘节点/边 | Neo4j 标签 `:Dataset`(StarRocks 表)、`:Source`(PG 表)、`:Transform`(Flink 作业/dbt/load 步骤)、`:Schedule`、`:OntologyType`；边 `(:Source)-[:SYNC]->(:Dataset)`、`(:Dataset)-[:DERIVES {transform}]->(:Dataset)` | Neo4j 已有(S3) |
| 自动生成 | 不手工埋：① 从 `schema.py` + `gen_flink_cdc_sql.py` 解析 source→sink 生成 SYNC/DERIVES；② dbt manifest.json 直接喂 DERIVES；把血缘做成 build 副产品 | 新增解析器 |
| 影响分析 | Cypher 遍历：下游 `MATCH (d:Dataset{name:$x})-[:DERIVES*]->(down)`；调试反向 | Cypher |
| **Marking 沿血缘传播** | **我们最缺**。给列打 `marking`(PII/SENSITIVE/INTERNAL/ORG:x)，落 Neo4j `(:Dataset)-[:HAS_MARKING]->(:Marking)`；传播 Cypher：凡 `(:Dataset)-[:DERIVES]->(down)` 自动继承上游 marking(并集)，除非边标 `stop_propagating`。执行点在只读 MCP（无对应 marking 权限则拒绝/脱敏 + 写审计） | 新增，接 3.4 |
| Marking 变更模拟 | 治理台选节点→"模拟加 PII"→跑传播 Cypher(不落库)→图上按 4 状态着色(applied/affected/unaffected/no data) | 治理台新 tab |
| 列检索 | 治理台搜列名→Cypher 查 `:Column{name}` 高亮含该列数据集(复刻 Frequent Columns) | 治理台 |
| 列到列推导血缘 | Foundry **没有**字段级推导图；若真要，自建：sqlglot/OpenLineage column-lineage facet 解析 SELECT 表达式 | 愿景 |

### 3.7 数据健康 → `dm/health/` 模块

新建 `dm/health/` = registry(JSON check 定义) + evaluator(定时跑写 JSONL) + notifier(钉钉/邮件) + MCP 只读工具 `health_status(resource)`。`pipeline/health.py` 的 `cdc_reconcile()`/`replication_slots()` 升级为其中两个 evaluator。

| Foundry 机制 | 我们复刻 | 现状 |
|---|---|---|
| Status: Job/Build | Flink/dbt/load 退出码 + 时间戳写 `logs/build_status.jsonl` | 新增薄封装 |
| Time: TSLU/Freshness | SQL `now() - max(_committed_at)` / `now() - max(updated_at)` | 直接实现 |
| Size: Row Count(+MAD) | `count(*)` + MAD 从最近 N 次结果 JSONL 现算 | 直接实现 |
| Content: PK/Null%/Range/Regex | 纯 SQL 聚合(只读 MCP 执行) | 直接实现 |
| Content: Approx Column Relation | 即 `cdc_reconcile()` 源(PG)汇(StarRocks)对账，升级为外键覆盖率/行数比 | **已有雏形** |
| Schema 类 + 4 枚举 | 从 `schema.py` 期望结构 vs `information_schema.columns`，默认 `COLUMN_ADDITIONS_ALLOWED` | 新增 |
| **构建期 abort 门禁** | **最大新增点**：Flink 落库前/dbt test 处执行断言，失败中断该表写入(staging→swap)，映射 FAIL；WARN 只记 JSONL | 新增 |
| Monitoring: stream/agent | 调度器连续失败计数 + Flink REST `/jobs/<id>/checkpoints`(lag/checkpoint) + psutil/node_exporter(CPU/磁盘) | Flink 已在主机 compose |
| 异常带 MAD | evaluator 内 `median + 1.4826*MAD*sigmas` | 纯计算 |
| 告警渠道 + level | notifier：站内恒发；`dm-dingtalk push` 作 webhook；level(nothing/all/only_critical) | 钉钉已有，接线即可 |
| 血缘联动健康 | Neo4j 节点挂 health 状态属性，下游异常沿边反查上游红点 | Neo4j 已有 |

check 定义 JSON schema（建议）：
```json
{
  "check_id": "chk_dwd_sales_order_freshness",
  "resource": {"kind": "starrocks_table", "name": "dwd.sales_order"},
  "category": "time", "type": "time_since_last_updated",
  "params": {"operator": "lte", "value": 60, "unit": "minutes",
             "ignore_empty_transactions": true,
             "median_deviation": {"sigmas": 3, "sample_builds": 30}},
  "severity": "critical",
  "escalate": {"after_consecutive_failures": 3},
  "schedule": {"mode": "custom", "cron": "*/10 * * * *"},
  "notify": {"in_platform": true, "webhook": "dingtalk", "level": "all_failures"},
  "issue": {"auto_create": true, "auto_close": true, "assignee": "data-oncall"}
}
```

**19 表默认套装**：每表挂 Job Status(critical) + TSLU(critical) + Row Count(moderate+MAD) + Primary Key(critical) + Schema=`COLUMN_ADDITIONS_ALLOWED`(critical)。CDC 链路额外挂 `Approximate Column Relation`/reconcile(critical) + Sync Freshness + Flink `Total lag`>1000 / `Liveness`≥2min。

### 3.8 报表 & Control Panel → 治理台 3 页

（`app/pages/` 已有 dashboard/warehouse/quality/governance/graph/sync/agent/docs）

- **对象工作台页**：Object Table → `st.dataframe`/`st.data_editor`（`column_config` 对应列格式/冻结/宽度），选中行=Active object(session_state)；Filter List → `st.sidebar` selectbox/multiselect/slider/date_input/text_input；Metric Card → `st.metric`；导出照抄 10k/200k 守护；Inline Action/Button Group → `st.button` 触发受控 Action(审批表单→写回 PG→CDC→StarRocks→JSONL)。
- **探索页**：图表聚合(Listogram/Histogram/Statistics Table) → StarRocks GROUP BY + `st.bar_chart`/plotly；点桶筛选写回 filter；Actions/Open In/Export 三按钮(Export=下载、Open In=跳图谱页做 Search-Around、1000 对象上限守护)。
- **管理者页**：角色矩阵(roles.yaml 定义 Owner/Editor/Viewer/Discoverer + operations 轻量映射，展示"用户-角色-资源")；**用量页**(把 compute-seconds 换成可测量：MCP 查询次数/耗时、agent token、StarRocks 查询耗时、Flink CDC 延迟；Budgets 照抄 Scope/Frequency/Amount/Thresholds%/Users to notify，超阈值发钉钉，可选硬阻断)；**审计页**(按 trace_id/category/denied 过滤，先按 time 过滤再聚合)；**权限判定回放**(输入 user_id+table 展示三道门逐步过/拒+原因，复刻 "Test security policies")。

### 3.9 AIP-Action → 无头 Claude + governed 写 MCP

- **Ontology 检索**：只读 MCP 已提供 Object Query(过滤/聚合/沿关系遍历)。补"每条消息→确定性检索→拼 system prompt"三通道：Ontology context(Neo4j/StarRocks 取 N 个 或 pgvector top-K，仅注入白名单属性)、Document context(pgvector top-K chunks)、Function-backed context(Python 函数返回 retrievedPrompt)。
- **governed Action 写回**：新建"只读 MCP 之外"的受治理写服务，把业务操作封装成 Action Type，绝不暴露裸 UPDATE。HTTP 形态仿 Palantir：`POST /actions/{actionType}/validate` 与 `/apply`。agent 决策前必须先 validate(INVALID 带 configuredFailureMessage 反问/终止)→VALID 才 apply→回写 PG→CDC 同步→审计。**库存校验（validate 不查现有对象）必须由 Object Query 侧独立算**。
- **tool calling**：无头 Claude 用 Anthropic 原生 tool use(≈native，可并行、省 token)为默认；后备模型走 prompted。
- **Evals**：`eval/run_eval.py` 已有 SQL 真值 + LLM-judge + 拒绝测试，高度同构。补：每用例跑 **≥3 次**再聚合 + 加 Rubric grader / Contains key details + 数值指标设 maximize 最小阈/minimize 最大阈 + 结果 Group by。
- **权限即审计**：agent 有效权限 = 调用者交集；靠 session_id(→purpose) 注入调用者身份，贯通"调用用户→有效权限→写回校验"。

**一句话路线**：① Source 对象化(含 cursor/markings/network_policy) + StarRocks External Catalog 补 virtual table → ② dbt 三段式 + 增量 + 构建期 abort 门禁 → ③ schema.py 升级对象类型注册表 + Neo4j 物化链接 → ④ PG 策略元表 + MCP 三道门(Markings 强制 + 列级 null) → ⑤ JSONL 升级 audit.3(category 化 + trace_id + denied) → ⑥ Neo4j 血缘并集传播 + 治理台判定回放/血缘 tab → ⑦ governed Action 写回(validate/apply + submission criteria) 闭环。

---

## 4. 关键决策点与 open questions

### 4.1 架构级决策点（需团队拍板）

| # | 决策 | 选项 | 倾向 |
|---|---|---|---|
| D1 | 写回落哪 | StarRocks(OLAP 事务弱) vs **PostgreSQL 源(OLTP)→CDC→StarRocks** | **写回落 PG 源**，由 CDC 流回 StarRocks，最贴合 Palantir"Action 经集成回写源系统" |
| D2 | 是否引入 Iceberg | StarRocks 分区近似(insert_overwrite) vs Iceberg(真时间旅行/分支) | 按数据量与"实验分支"实际需求；PoC 阶段分区近似可能够用，避免运维成本 |
| D3 | 行级安全过滤粒度 | 按"表"注入 WHERE vs 按"本体对象"过滤 | 若 Neo4j 只做图查询、未建完整对象层，先在 MCP **按表注入 WHERE** 更现实 |
| D4 | Markings 实现选型 | StarRocks 列级 governance 标 vs PG RLS vs 查询层拦截 | 只读快照 + Streamlit 组合下，**MCP 查询层拦截**最稳(唯一入口=边界终点) |
| D5 | 事件驱动增量 | 纯 dbt run(全图) vs Dagster sensor + dbt asset selection(model 级) | 要达 Foundry"事件只重算受影响子图"需 Dagster；PoC 可先 cron |
| D6 | CBAC 多级密级 | 需要 vs 不需要 | 制造业场景大概率**用不到军规 CBAC**，标准 marking 足够 |
| D7 | 用量预算主指标 | MCP 查询耗时 / agent token 数 / StarRocks CPU 时 | 需与用户确认 |
| D8 | llmInference 脱敏 | 记全文 vs 摘要/哈希 | 制造 prompt 含业务敏感数据，需与用户决策隐私/审计权衡 |

### 4.2 需实测确认的技术边界（open questions）

**连接器**：① Foundry worker 模式凭证具体存哪、用谁密钥解(KMS?)文档未明；② agent 出站端口确切清单/是否支持 proxy chaining；③ 每连接器 batch/incremental/streaming/export capability 矩阵官方无对照表；④ 增量游标推进与事务 commit 的原子边界(先 commit 数据还是先推游标)、at-least-once vs exactly-once 保证级别；⑤ JDBC 增量只允许**单个 `?`**，复合游标(双列断点)需自行设计。

**转换**：⑥ v1 vs v2 增量语义实际差异(影响 dbt append/merge/insert_overwrite 取舍)；⑦ `'previous'` 读模式"首次/大改后返回空"的精确判定条件；⑧ `snapshot_inputs` 与 `require_incremental` 同时设时的交互；⑨ `strict_append=True`(纯 APPEND) 与 StarRocks 主键表 upsert 的冲突——哪些表走 append/哪些走 merge 需按表分类；⑩ Foundry 事件驱动只重算受影响子图在 dbt 上靠 `state:modified`+defer 或 Dagster 逼近的完整度。

**本体**：⑪ OSv2 每对象类型属性数上限、对象类型数上限(官方只明确 String 12MB/Array 100k)；⑫ 确定性主键与源 PG 主键一一对应且不随重导变化(决定 writeback 对齐)；⑬ Action 事务原子性(一次改多对象是否整体回滚)——需实测 PG 事务边界；⑭ Action parameter 完整类型枚举(官方未单页给全)；⑮ Value Type 约束校验时机(写入 vs 索引 vs action 提交)——影响放 MCP 写工具还是 StarRocks 约束层。

**权限**：⑯ granular policy 权重上限"单策略<10000"vs"object+property 合计<10000"是否同一/分别(可先取保守合计 10000)；⑰ "≤10 比较"vs"权重 10000"哪个先触顶；⑱ marking 沿血缘并集传播的触发点(Foundry 每次 build 自动；我们无统一 orchestrator，用建模作业钩子还是定时 reconcile)。

**审计**：⑲ audit.3 官方未给完整实例，`entities` 是纯 RID list 还是带类型对象需实测校准；⑳ `result` 完整枚举(SUCCESS/ERROR/UNAUTHORIZED 之外是否有 PARTIAL/DENIED)；㉑ 完整 category 全列表(>100)逐条字段需浏览器抓 SPA 页(我们只需 6-8 个)。

**血缘**：㉒ Marking 继承后端是全量重推还是增量(19 表小，放大后性能阈值)；㉓ `stop_propagating` 审批工作流在我们栈落哪(GitHub PR? 治理台人工确认?)；㉔ 模拟态大图交互延迟 + "access affected"多跳边界；㉕ RV 不可入转换的护栏我们需自建(官方靠平台强制)；㉖ provenance 双来源(Dataset+对象类型)合并规则(并集? 冲突取严?)。

**数据健康**：㉗ 构建期 abort 事务粒度(StarRocks/Flink 无"整 build 单事务"，倾向 staging→swap)；㉘ MAD 基线冷启动(样本<10 次是否只 warn)；㉙ Custom Schedule 分钟级 freshness 对 StarRocks 只读查询压力(19 表×多检查×每分钟)；㉚ Approximate 跨表列相似度无 StarRocks 内建(自研 or 降级精确对账)；㉛ 告警去抖(多表同时 fail 按血缘上游根因聚合)；㉜ Schema 类型三方映射(Foundry Integer/String vs StarRocks TINYINT/VARCHAR vs PG 源类型)需固化避免误报。

**报表/Control Panel**：㉝ audit.3 真实字段嵌套需实测；㉞ operation 全集官方未穷举(roles.yaml 取业务够用最小子集)；㉟ Object Explorer "Open In"/"Export" 完整目标清单随 workspace 配置变；㊱ compute-seconds → 我们栈无官方等价计量单位需自定义。

**AIP**：㊲ Native tool calling 支持哪些具体 Palantir 模型(官方只说"a subset")，我们 Anthropic 原生 tool use 是否与"并行多工具"语义完全等价(并发写 Action 顺序/冲突)；㊳ AIP Evals 多次运行聚合算法(多数投票? 平均? 阈值口径)官方未给公式；㊴ Apply Action 的 batch/transaction 模式与一次 apply 内多对象编辑原子性/回滚；㊵ 库存校验放 submission criteria(objectQueryResult 约束)还是 agent 决策逻辑——官方对 objectQueryResult constraint 能力边界未细说；㊶ Function rule"存在时不可配其他 rule"下复杂多对象写回是否必须全走 Ontology edit 函数；㊷ Function-backed retrieval 的 retrievedPrompt token 上限 + 语义 chunk 默认 K 值/切分策略(pgvector 侧自定并 eval 调参)。

---

## 5. 关键来源 URL

### 连接器
- https://www.palantir.com/docs/foundry/data-connection/core-concepts
- https://www.palantir.com/docs/foundry/data-connection/architecture
- https://www.palantir.com/docs/foundry/data-connection/foundry-worker-vs-agent-worker
- https://www.palantir.com/docs/foundry/available-connectors/other-source-types
- https://www.palantir.com/docs/foundry/building-pipelines/create-incremental-syncs
- https://www.palantir.com/docs/foundry/data-integration/virtual-tables
- https://www.palantir.com/docs/foundry/transforms-python/tables-compute-pushdown

### 转换 / 数据集
- https://www.palantir.com/docs/foundry/transforms-python/transforms-python-api
- https://www.palantir.com/docs/foundry/api-reference/transforms-python-library/api-incremental
- https://www.palantir.com/docs/foundry/transforms-python/incremental-overview
- https://www.palantir.com/docs/foundry/data-integration/datasets
- https://www.palantir.com/docs/foundry/building-pipelines/recommended-project-structure
- https://www.palantir.com/docs/foundry/building-pipelines/triggers-reference
- https://www.palantir.com/docs/foundry/transforms-python/data-expectations-reference

### 本体
- https://www.palantir.com/docs/foundry/ontology/overview
- https://www.palantir.com/docs/foundry/architecture-center/ontology-system
- https://www.palantir.com/docs/foundry/object-link-types/base-types
- https://www.palantir.com/docs/foundry/object-link-types/create-object-type
- https://www.palantir.com/docs/foundry/object-link-types/link-types-overview
- https://www.palantir.com/docs/foundry/action-types/rules
- https://www.palantir.com/docs/foundry/action-types/submission-criteria
- https://www.palantir.com/docs/foundry/object-indexing/data-restrictions
- https://www.palantir.com/docs/foundry/ontology-sdk/python-osdk

### 权限
- https://www.palantir.com/docs/foundry/security/overview
- https://www.palantir.com/docs/foundry/security/markings
- https://www.palantir.com/docs/foundry/security/projects-and-roles
- https://www.palantir.com/docs/foundry/security/classification-based-access-controls
- https://www.palantir.com/docs/foundry/platform-security-management/manage-granular-policies
- https://www.palantir.com/docs/foundry/platform-security-management/manage-markings
- https://www.palantir.com/docs/foundry/object-permissioning/object-security-policies
- https://www.palantir.com/docs/foundry/object-permissioning/ontology-permissions-legacy
- https://www.palantir.com/docs/foundry/object-link-types/mandatory-control-properties
- https://www.palantir.com/docs/foundry/action-types/permissions
- https://www.palantir.com/docs/foundry/security/download-controls
- https://blog.palantir.com/purpose-based-access-controls-at-palantir-f419faa400b3

### 审计
- https://www.palantir.com/docs/foundry/security/audit-logs-overview
- https://www.palantir.com/docs/foundry/security/audit-log-categories
- https://www.palantir.com/docs/foundry/security/monitor-audit-logs
- https://github.com/palantir/tracing-java
- https://github.com/openzipkin/b3-propagation
- https://www.palantir.com/docs/foundry/api/audit-v2-resources/log-files/list-log-files
- https://www.palantir.com/docs/foundry/aip-observability/trace-view
- https://community.palantir.com/t/how-to-query-audit-logs-v3-via-api-in-a-lightweight-transform/6093

### 血缘
- https://www.palantir.com/docs/foundry/data-lineage/overview
- https://www.palantir.com/docs/foundry/data-lineage/node-coloring
- https://www.palantir.com/docs/foundry/data-lineage/see-impact-marking-changes
- https://www.palantir.com/docs/foundry/data-lineage/find-column
- https://www.palantir.com/docs/foundry/building-pipelines/remove-inherited-markings
- https://www.palantir.com/docs/foundry/security/restricted-views
- https://www.palantir.com/docs/foundry/object-edits/materializations
- https://www.palantir.com/docs/foundry/api/v2/admin-v2-resources/markings/create-marking

### 数据健康
- https://www.palantir.com/docs/foundry/health-checks/check-types
- https://www.palantir.com/docs/foundry/data-health/checks-reference
- https://www.palantir.com/docs/foundry/health-checks/check-evaluation
- https://www.palantir.com/docs/foundry/maintaining-pipelines/define-data-expectations
- https://www.palantir.com/docs/foundry/monitoring-views/rules-reference
- https://www.palantir.com/docs/foundry/data-health/overview

### 报表 & Control Panel
- https://www.palantir.com/docs/foundry/workshop/widgets-object-table
- https://www.palantir.com/docs/foundry/workshop/widgets-filter-list
- https://www.palantir.com/docs/foundry/workshop/widgets-metric-card
- https://www.palantir.com/docs/foundry/object-explorer/explore-charts
- https://www.palantir.com/docs/foundry/object-explorer/apply-actions
- https://www.palantir.com/docs/foundry/administration/control-panel
- https://www.palantir.com/docs/foundry/platform-security-management/manage-roles
- https://www.palantir.com/docs/foundry/resource-management/usage-types
- https://www.palantir.com/docs/foundry/resource-management/budgets

### AIP
- https://www.palantir.com/docs/foundry/aip/overview
- https://www.palantir.com/docs/foundry/logic/overview
- https://www.palantir.com/docs/foundry/agent-studio/tools
- https://www.palantir.com/docs/foundry/agent-studio/retrieval-context
- https://www.palantir.com/docs/foundry/aip-evals/create-suite
- https://www.palantir.com/docs/foundry/action-types/overview
- https://www.palantir.com/docs/foundry/api/ontology-resources/actions/apply-action
- https://www.palantir.com/docs/foundry/api/ontology-resources/actions/validate-action
- https://www.palantir.com/docs/foundry/ontology-sdk/typescript-osdk
- https://blog.palantir.com/connecting-ai-to-decisions-with-the-palantir-ontology-c73f7b0a1a72

---

*本 spec 由 9 维度实装级调研 + 3 维度对抗验证（permissions / audit / lineage，均 confirmed=true）合并而成。对抗验证发现的 4 处硬错误（旧本体 4 Role、audit `name` 全大写、Node coloring 6 模式、Markings/OrgMarkings 双参数）与若干机制归属/措辞更正已全部吸收进正文并以 **⚠ 更正** 标注。*
