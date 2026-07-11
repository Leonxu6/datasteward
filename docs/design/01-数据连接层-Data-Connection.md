# 01 · 数据连接层（Data Connection）

> Palantir Foundry 中把**外部系统的数据搬进平台、也能推回外部**的那一层，官方叫 **Data Connection**。它统一了"连什么系统、用什么凭证、走什么网络、搬哪些数据、怎么增量、产物落成什么"这一整套问题。
>
> 对应到DataSteward 平台：就是我们的**连接器层**——当前的 `gen_flink_cdc_sql.py`（Flink CDC 从 PostgreSQL 抽数）、规划中的只读 MCP 连接器与 JSONL 审计、以及尚未对象化的"源配置"。本文既讲 Palantir 的机制，也给出我们栈上的复刻映射。

---

## 一、解决什么问题（第一性原理）

任何数据平台，第一道门槛都是"数据不在我这里"。业务数据散落在 ERP（U8）、数据库（SQL Server / PostgreSQL）、对象存储、SaaS、文件里。要让平台能分析、能建血缘、能治理，必须先把这些数据**可靠、可审计、可增量、可治理地**接进来。

这一层要同时解决五件事，缺一不可：

1. **连接定义**：连哪个系统？URL/host/port/region 是什么？用什么凭证？走什么网络？——需要一个稳定的、可复用的"连接实例"抽象，而不是把这些散落在各处脚本里。
2. **凭证保管**：外部系统的密码/token 必须加密存储、运行时解密、用完即删、审计里绝不出现明文。
3. **网络与访问治理**：源系统往往在私网；平台不应对外主动发起入站连接；源的密级（Markings）必须随数据传播到下游，无权限的人看不到下游数据。
4. **搬数语义**：一次搬全量还是增量？增量靠什么游标？失败了会不会留半截脏数据？——需要**原子事务 + 可恢复游标**。
5. **血缘根**：搬进来的产物应当和后续加工用同一种抽象，血缘才能自动生成，而不是断在"入库"这一步。

Palantir 的答案是把这五件事收敛成**四个核心对象 + 两种运行时 + 一套治理规则**。下面逐层拆解。

---

## 二、Palantir 怎么做（机制）

### 2.1 四对象模型：Source / Connector / Sync / Export（+ Virtual table）

Data Connection 的全部功能围绕四个对象展开，再加一个不落地的 Virtual table。

| 对象 | 定位 | 内容 |
|---|---|---|
| **Source** | 外部系统的**连接实例** | 连接参数（URL/host/port/region）+ 凭证 + 网络策略 + 打标（Markings/Organizations） |
| **Connector / Source type** | 针对**某类系统**的集成器 | 官方预置 ~200+（见第三节全表）；未列出的关系库统一走 JDBC (custom)；通用协议 REST/GraphQL/OData/Generic/JDBC |
| **Sync** | 真正的**搬数动作** | batch / incremental / streaming / media / file 五类；每次 run 写在输出 Dataset 的**单个事务**里 |
| **Export** | **反向**把 Foundry 数据推回外部 | 实现双向（平台 → 外部系统） |
| **Virtual table** | **不落地、直查外部** | Snowflake/BigQuery/Databricks/Iceberg/Delta；支持 compute pushdown |

**Source（源）**：外部系统的连接实例。在 Data Connection app 里建源的流程固定为：选 source type → 填连接细节（URL/host/port…）→ 选运行时（Foundry worker / agent worker）→ 录凭证 → 指定 network policy + Markings/Organizations。Source 把"连接细节、凭证、网络、密级"打包成一个可复用、可治理的对象。

**Connector / Source type（连接器）**：针对某一类外部系统的集成器。官方预置约 200+（全列表见第三节）。凡未列出的关系型数据库，统一选 **JDBC (custom)**；通用协议层还有 REST APIs、GraphQL、OData、Generic connector、JDBC。

**Sync（同步）**：真正搬数的动作，五种类型——
- **Batch sync**：周期性全量或增量拉取；单事务写输出 Dataset；可手动跑或挂到 Foundry build 系统的 schedule。**建 batch sync 会自动创建输出 Dataset。**
- **Incremental sync**：基于游标的增量（详见 2.5）。
- **Streaming sync**：Flink 驱动，接 Kafka / Kinesis / Pub-Sub。
- **Media set sync**：图像 / 文档 / 音频 → media set。
- **File-based sync**：CSV / JSON / Excel / Parquet。

> **事务原子性（关键）**：每次 sync run 都写在输出 Dataset 的**单个事务**里。中途失败 → 事务 abort → Dataset 保持运行前状态，**不留半截脏数据**。

**Export（导出）**：反向把 Foundry 数据推回外部系统，使整个连接层是双向的。

**Virtual table（虚拟表）**：不把数据搬进 Foundry，而是**按查询直读外部**（Snowflake / BigQuery / Databricks / 云存储 Iceberg & Delta）。当源由这些系统 backed 时，可做 **compute pushdown**——把 Foundry 的 transform 下推到源侧执行（走各家 Spark connector 的谓词下推）。**注意：`@incremental` 装饰器在 pushdown 下不支持。**

### 2.2 两种运行时：Foundry worker + agent proxy（新，推荐）vs Agent worker（legacy）

连接的实际执行有两种架构，核心差异是**计算在哪跑**。

**（1）Foundry worker + agent proxy（推荐）**
- agent 向 Foundry **发起** websocket 连接（出站）。
- 所有数据连接与计算能力由 **Foundry worker**（隔离容器、可弹性伸缩）执行，经 websocket 与外部系统通信。
- **agent 只当纯网络隧道，不做任何数据处理**。
- 好处：升级 / 扩容 / 打补丁**集中在 Foundry 侧**，客户私网里只需维护一个退化为隧道的 agent。

**（2）Agent worker（legacy）**
- agent 常驻客户私网，**出站单向 HTTPS 轮询** Foundry 取任务。
- 任务由 **agent 自己执行**抽取，结果经同一条单向连接回传。
- 无新功能开发，但仍支持。（早期的 Direct connection 已废弃。）

**网络方向（两种模式共同点）**：
- Foundry **不向外部系统发起任何入站连接**；外部系统无需为 Foundry 开入站。
- agent 主机需对目标外部系统有**出站连通性**，且外部系统需允许来自 **agent 主机**的入站。

**高可用（HA）**：
- 多 agent 可对多个外部系统做负载均衡。
- agent proxy 可配多 agent，做**交替维护窗口**以避免停机。

**agent 运行时**：JVM heap 在 agent settings 页配置，**默认 1 GB**。

### 2.3 凭证保管（credential vault 机制）

- **agent worker 模式的加密链路**：录凭证时**不是** Foundry 侧加密，而是在**浏览器里用分配给该源的每个 agent 的公钥加密**后再送 Foundry；加密后的凭证存 Foundry，**只有对应 agent 用私钥能解**。
- **加密算法**：外部系统凭证在平台以 **AES-128-GCM** 加密，密钥存 agent 上。能力执行时，agent 从 Foundry 取加密凭证 → 本地解密查询 → **解密后凭证用完自动从内存删除**。
- **agent 集合变更 = 必须重录凭证**：agent 集合变了要重录；agent 用全新下载链重装则凭证不自动迁移，须先**恢复旧 agent 的加密密钥**，否则全部重录。
- **认证方式**：用户名/密码、OAuth 2.0 / OIDC、API key/token、云原生 IAM 角色。
  - **REST 源的 OAuth Client Credentials**：配 token endpoint 域 + resource API 域；`client_id`/`client_secret` 作为源上的 **additional secrets** 存储；换取短时 access token 作为 bearer 放进 `Authorization` header。

### 2.4 源打标 + 网络隔离（连接治理）

**Markings / Organizations（源打标传播）**：
- 作为**额外访问控制**加在 Source 上。
- 会**传播到该源 syncs 产出的所有 Dataset**——用户若不具备源上的**全部** Markings/Organizations，就看不到任何下游 Dataset 的数据。这是治理的核心机制：密级随数据流动，不靠人工在每层重设。

**network egress policy（网络出口策略）**：
- Foundry worker 源**建源时必须指定网络策略**。
- 客户自管 egress 用容器网络（**Cilium / eBPF**）对**单个 workload** 施加防火墙规则。
- 支持 **wildcard**（`*.domain.com`）allowlist 整个子域层级。
- 给某个用户 workload 分配策略，需要该 egress policy 的 **Importer 权限**（按策略在 Manage Sharing 授予）。

**权限模型**：
- 默认角色：**Owner / Editor / Viewer / Discoverer**。
- 含 source 的 Project 的 **Editor** 能建/改 sync、建 Webhook。
- **风险提示**：持有 source/agent 查看+编辑权限的人应当是**可信的管道开发者**——sync 若源凭证允许，可反向改源系统（删 S3/Directory 文件、执行任意 SQL drop 库）。

### 2.5 批量 vs 增量 / CDC + 落 raw Dataset

**Batch sync**：全量或增量周期拉；单事务写输出 Dataset；可手动跑或挂 Foundry build schedule。

**Incremental sync（stateful，APPEND 风格）**：
- **Single field 模式**：目标列 **>= 已导入最大值**时导入。
- 必须提供**单调递增列**（timestamp 或 id）+ **初始值**；平台跟踪已同步的最新值，只带更新的行。

**JDBC 增量的具体写法（本层最硬的一条细节）**：
- 选好增量列后，在 sync 配置页的 SQL 里加 `?` 占位符——`?` 会被替换为增量值，**且仅允许一个 `?`**。
- 示例：
  ```sql
  SELECT * FROM orders WHERE id > ?
  ```
- 首次运行时带入**初始值**，只 ingest 大于初始值的行；之后平台自动持久化并推进游标。

**APPEND vs SNAPSHOT 事务**：
- 入 Foundry 的数据应由 **APPEND** 事务组成（**只带新数据**）。
- 也可在管道里从 SNAPSHOT 配置的 sync **派生出 APPEND-only 的 Dataset**。
- 源不支持增量时，用 **SNAPSHOT** 做整表替换。
- 可在 Dataset 事务历史的 **Custom Metadata** 里查看 **`incrementalMetadata`** 块。

**CDC / 版本化源**：
- 核心概念含 **Change Data Capture**（库级变更跟踪）。
- 若源表格式支持版本（**Delta / Iceberg**），Foundry 能**检测变更、只在必要时触发下游 build**。

**落 raw Dataset（血缘根）**：sync 的产物就是 **Dataset**——与 transform 的输入/输出是**同一抽象**，因此血缘自动生成，不会断在"入库"这一步。

---

## 三、字段 / 配置 / 清单细节（硬细节）

> 本节是本文档的价值所在：连接器全表、增量 SQL 写法、凭证机制等硬细节照实保留，便于长期查阅与复刻对照。

### 3.1 连接器 / Source type 分类全列表（~200+，官方 Available connectors）

> 说明：数字是厂商口径、随版本变，以 `docs.palantir.com/available-connectors` 当期页为准。以下为按类整理的清单。

- **数据库 / 数仓**：AlloyDB, Amazon DynamoDB, Amazon Redshift, Apache CouchDB, Apache HBase, Apache Hive, Apache Phoenix, Azure Cosmos DB, Azure Synapse, Azure Table Storage, BigQuery, Cassandra, CockroachDB, Couchbase, Databricks, Db2, EnterpriseDB, Google Spanner, Greenplum, HDFS, IBM Cloud Data Engine, MarkLogic, Microsoft Access, Microsoft SQL Server (+Analysis Services), Oracle Database, PostgreSQL, Presto, Redis, SAP HANA XSA, SingleStore, Snowflake, Spark SQL, SybaseIQ
- **对象 / 文件存储**：Agent-level filesystem, Amazon S3, ABFS (Azure Blob Filesystem), Google Cloud Storage, IBM Cloud Object Storage, OneLake, SFTP, SMB, FTP/FTPS, Directory
- **流 / 消息**：Amazon Kinesis, Apache Kafka, Google Pub/Sub, Twilio
- **ERP / 财务**：ADP, Avalara, Certinia, Epicor Kinetic, Oracle Fusion Cloud (Financials/HCM/SCM), QuickBooks (Desktop/Online/POS), SAP ERP, SAP SLT, SAP Ariba, SAP Business One, SAP ByDesign, SAP Cloud for Customer, SAP Fieldglass, SAP Concur, Xero, Zoho Books, Tally, Acumatica, MS Dynamics GP/NAV/365 Business Central
- **CRM / 销售**：Bullhorn, Highrise, HubSpot, MS Dynamics CRM/365, Outreach, Pipedrive, Salesforce, Salesloft, SugarCRM, SuiteCRM
- **营销 / 广告**：Act-On, Adobe Analytics, Adobe Commerce, Facebook Ads, Google Campaign Manager, LinkedIn Marketing, Marketo, Microsoft Ads/Bing, Salesforce Marketing Cloud (+Account Engagement), Snapchat Ads, Twitter Ads
- **HR**：Paylocity, SAP SuccessFactors
- **会计 / 支付**：Authorize.Net, Exact Online, FreshBooks, MYOB, PayPal, Reckon, Sage (50/200/300/Business Cloud), Square, Stripe, TaxJar, Wave Financial, Zuora
- **项目 / 协作管理**：Asana, Basecamp, Monday, MS Planner/Project, Smartsheet, Trello
- **工单 / 支持**：Freshdesk, Jira Service Management, Zendesk
- **通信 / 协作**：Gmail, MS Exchange/Office365/Teams, Slack
- **文档 / 内容**：Confluence, DocuSign, MS OneNote/SharePoint (+Online/Excel)
- **BI**：Tableau CRM Analytics, SAP BusinessObjects BI, MS Power BI XMLA
- **电商**：BigCommerce, eBay (+Analytics), Shopify, WooCommerce, WordPress, ShipStation
- **社媒**：Facebook, Instagram, LinkedIn, Pinterest, YouTube Analytics
- **目录 / 身份**：Azure AD, Google Contacts/Directory, LDAP, Directory
- **开发**：GitHub
- **协议 / 通用**：REST APIs, GraphQL, OData, JDBC (custom), Generic connector, RSS, Email (via listeners)
- **专用 / 工业**：PI System（OSIsoft 工业时序）, Veeva Vault, Palantir Foundry（Foundry-to-Foundry）, SAS Data Sets/Xpt

> 关键取舍：**未列出的关系库 → 统一选 JDBC**；**SAP 有专门的 SAP ERP + SAP SLT（近实时）+ 自定义 SAP source**。

### 3.2 增量 sync 配置形态（JDBC 示例）

| 配置项 | 取值 |
|---|---|
| 增量列 | 单调递增列（`id` / `updated_at`），并配**初始值** |
| SQL | `SELECT * FROM orders WHERE id > ?`（`?` **唯一**，替换为已同步最大值） |
| 事务 | **APPEND**（增量）/ **SNAPSHOT**（全量替换） |
| 元数据 | Dataset 事务历史 → Custom Metadata → **`incrementalMetadata`** 块 |

### 3.3 REST API 源配置形态

- **字段**：base URL、authentication、可选 port。
- **OAuth Client Credentials**：配 token endpoint 域 + resource API 域；`client_id`/`client_secret` 存为 source 上的 **additional secrets**；换取的 bearer token 放进 `Authorization` header。
- **用途**：Webhook / Workshop 按钮经 Action 直接打外部 REST（**Webhook 走 REST API source type**）。

### 3.4 连接架构关键参数

| 参数 | 取值 |
|---|---|
| Foundry worker | 隔离容器、弹性伸缩，经 websocket 与外部通信 |
| agent（proxy 模式） | 纯隧道，出站发起 websocket；**无 Foundry → 外部入站** |
| agent worker（legacy） | 出站单向 HTTPS 轮询，agent 本地执行 |
| JVM heap | agent settings 页配置，**默认 1 GB** |
| 凭证加密 | **AES-128-GCM**，浏览器侧 agent 公钥加密，私钥 agent 本地解密、用完删 |

### 3.5 Virtual table + pushdown

- **源**：
  - Snowflake（Horizon Catalog Iceberg REST + credential vending + external volumes）
  - Databricks（Unity Catalog external access + Unity REST + Iceberg REST catalog）
  - BigQuery
  - 云存储 Iceberg / Delta
- **pushdown**：走各家 Spark connector 的谓词下推；**`@incremental` 在 pushdown 下不支持**。
- **版本化源**（Delta / Iceberg）：自动检测变更、触发下游 build。

---

## 四、映射到DataSteward 栈（我们怎么复刻）

我们的栈：StarRocks 数仓 / PostgreSQL 源 / Flink CDC / Neo4j 图 / pgvector / 只读 MCP 连接器 + JSONL 审计 / 无头 Claude / Streamlit 治理台。逐条对齐 Palantir Data Connection：

### 4.1 Source 对象化（当前最大缺口）

现状：连接元数据**硬编码**在 `gen_flink_cdc_sql.py`（`host='dm-postgres'`、`slot.name=flink_<t>`）。

目标：抽出一个 **Source 配置对象**（YAML / 表），把"哪些表、游标列、凭证、密级"从 SQL 里解耦——这正对应 Palantir 的 Source：

```yaml
source_id: pg_erp_main
type: postgres            # postgres / rest / file
host: dm-postgres
port: 5432
credentials_ref: vault://pg_erp_main   # 不落明文
network_policy: sg-erp-egress
markings: [confidential]
tables: [sales_order, material, ...]
cursor_col: updated_at
initial_value: "2026-01-01T00:00:00"
```

### 4.2 Sync 类型语义

- **Streaming / Incremental → 已有 Flink CDC（postgres-cdc）**：
  - WAL 的 **LSN = Palantir 的高水位游标**。
  - `scan.incremental.snapshot.enabled=true` 先全量快照再切增量 = 官方"全量 → 增量"开关。
  - 补上显式 **APPEND vs SNAPSHOT 标注**：StarRocks **主键模型 = SNAPSHOT/UPSERT 语义**，**明细模型 = APPEND**。
- **Batch / JDBC 增量 → 对未上 CDC 的源（如 U8/ERP）**：
  - 照 Palantir 写法做**参数化 SQL**：`WHERE updated_at > :cursor`。
  - 游标持久化到一张 **`sync_state` 表**（`source_id, table, last_cursor, last_run_ts`），失败可恢复。
- **File sync**：落 CSV / Parquet 到 StarRocks（**Broker Load / Stream Load**）。

### 4.3 事务原子性

Palantir 每次 sync 单事务、失败 abort。我们的复刻：
- StarRocks 用 **Stream Load 的 label 幂等 + 事务**，失败不 commit；
- 或先落 **staging 表 → 原子 swap**，保证不留半截脏数据。

### 4.4 凭证保管

现状：凭证可能在 compose env / 明文。最小复刻：
- 凭证**加密存储**（SOPS/age 或 PG 里 pgcrypto），运行时解密、**不落日志**；
- **MCP 连接器只读，审计里绝不记凭证**；
- 对齐 Palantir 的"**用完即删、审计不含凭证**"。

### 4.5 源打标传播（Markings）

- 给 Source 配置加 `markings[]`；落库时写进 StarRocks 表的一个 **governance 列**，或维护一张 `dataset_marking` 映射表；
- Streamlit 治理台**查询前按用户属性做行/列过滤**（PG RLS 或查询层拦截）；
- 复刻"**Markings 随数据传播、无权看不到下游**"。

### 4.6 网络隔离

- 现有 **4 口 SSH 隧道 + compose 容器内主机名直连** = 自建 **agent worker**（计算 Flink 与源同私网）。
- Palantir 演进方向提示：长期可把 **Flink 计算与"隧道"分离**，隧道只转发（对齐 Foundry worker + agent proxy）。
- egress allowlist 可落在**阿里云安全组 / compose 网络策略**上。

### 4.7 Virtual table

- **StarRocks External Catalog（JDBC / Iceberg / Hive catalog）= Palantir virtual table + pushdown 的天然对应**——不落地直查 PG/Iceberg，谓词下推。
- 这是**低成本、高价值**的一块，优先做。

### 4.8 审计 + 血缘

- **MCP 只读 + `audit_log.jsonl`** 已实现"访问点审计"。
- `sync 产物 → transform → StarRocks 表`这条边可发 **OpenLineage 事件喂 Neo4j（图）**，复刻 Palantir"血缘是 Dataset 抽象的副产品"。
- `session_id` 关联已具备回放能力。

### 4.9 一句话路线

① 把 CDC 连接元数据抽成 **Source 对象**（含 cursor/markings/network_policy）；② 给非 CDC 源加**参数化 SQL 增量 + `sync_state` 游标持久化**；③ 落库走**原子事务**（staging swap / Stream Load label）；④ 用 **StarRocks External Catalog** 补 virtual table；⑤ **Markings 列 + Streamlit 行级过滤**复刻源打标传播。

---

## 五、Open questions（待实测 / 决策）

1. **凭证公钥加密的确切实现**：官方明确 agent worker 模式浏览器用 agent 公钥加密、AES-128-GCM；但 **Foundry worker 模式（推荐）下凭证具体存哪、用谁的密钥解密（Foundry 侧 KMS?）** 未在检索片段里明确，需实测或读 architecture 全文确认。
2. **agent 出站端口的确切清单**：确认走 443/HTTPS 与 websocket，但**是否还需其他端口、是否支持 HTTP 代理链（proxy chaining）** 未取到确切配置字段（agent-proxy 配置页 JS 渲染未抓到正文）。
3. **每个连接器的 capability 矩阵**：官方无公开的"哪个连接器支持 batch/incremental/streaming/export"逐项对照表，需逐个连接器页确认（如 Oracle/Salesforce 是否支持 export、是否支持 CDC）。
4. **~200+ 连接器的准确总数与 changelog**：数字是厂商口径、随版本变，以 `docs.palantir.com/available-connectors` 当期页为准（本文靠搜索索引拼出，可能有遗漏/过期，如 Odoo/Mailchimp/Google Sheets 等出现在部分片段）。
5. **增量游标的失败恢复语义细节**：官方说平台持久化游标、失败可恢复，但**游标推进与事务 commit 的原子边界**（先 commit 数据还是先推游标）、**重复/漏数据的确切保证级别**（at-least-once? exactly-once?）需实测。
6. **Virtual table 的写回与 external volume 细节**：Snowflake/Databricks 经 Iceberg REST catalog "read and write" 底层存储，**写路径的一致性/事务保证**、以及**能否用 StarRocks External Catalog 完全等价**，需在我们栈上实测。
7. **我们栈上 Markings 传播的实现选型**：**StarRocks 列级 governance 标 vs PG RLS vs 查询层拦截**——哪种在只读快照 + Streamlit 组合下最稳、性能可接受，需决策 + POC。
8. **JDBC 增量 SQL 只允许单个 `?` 占位符**：**复合游标（如 `(updated_at, id)` 双列断点）在 Palantir 原生怎么处理**未明；我们若需复合游标要自行设计。

---

## 六、来源

- https://www.palantir.com/docs/foundry/data-connection/core-concepts
- https://www.palantir.com/docs/foundry/data-connection/architecture
- https://www.palantir.com/docs/foundry/data-connection/foundry-worker-vs-agent-worker
- https://www.palantir.com/docs/foundry/data-connection/agent-configuration-reference
- https://www.palantir.com/docs/foundry/data-connection/agent-worker
- https://www.palantir.com/docs/foundry/data-connection/agent-proxy
- https://www.palantir.com/docs/foundry/data-connection/set-up-source
- https://www.palantir.com/docs/foundry/data-connection/set-up-agent
- https://www.palantir.com/docs/foundry/data-connection/set-up-sync
- https://www.palantir.com/docs/foundry/data-connection/permissions
- https://www.palantir.com/docs/foundry/available-connectors/other-source-types
- https://www.palantir.com/docs/foundry/available-connectors/custom-jdbc-sources
- https://www.palantir.com/docs/foundry/data-integration/source-type-overview
- https://www.palantir.com/docs/foundry/data-integration/foundry-provided-drivers
- https://www.palantir.com/docs/foundry/building-pipelines/create-incremental-syncs
- https://www.palantir.com/docs/foundry/data-connection/optimize-jdbc-syncs
- https://www.palantir.com/docs/foundry/data-integration/virtual-tables
- https://www.palantir.com/docs/foundry/transforms-python/tables-overview
- https://www.palantir.com/docs/foundry/transforms-python/tables-compute-pushdown
- https://www.palantir.com/docs/foundry/iceberg/managed-virtual
- https://www.palantir.com/docs/foundry/available-connectors/rest-apis
- https://www.palantir.com/docs/foundry/available-connectors/oracle
- https://www.palantir.com/docs/foundry/available-connectors/snowflake
- https://www.palantir.com/docs/foundry/available-connectors/databricks
- https://www.palantir.com/docs/foundry/administration/configure-egress
- https://www.palantir.com/docs/foundry/api/v2/connectivity-v2-resources/virtual-tables/virtual-table-basics
