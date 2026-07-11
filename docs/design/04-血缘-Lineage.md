# 04 · 数据血缘（Lineage）

> **一句话定位**：血缘是"谁产谁"的有向依赖图——它同时回答影响分析（改上游炸哪些下游）、调试溯源（异常从哪来）、合规来源（数据可追溯）三个问题，并且是**安全标签（Marking）随数据自动传播**的载体。
> **对应我们平台的哪一层**：Neo4j 存血缘图（我们已有），`pipeline/lineage.py` 从 transform 注册表自动登记边，MCP 连接器层落"安全随血缘传播"的执行点，治理台 Streamlit 画图 + 做 Marking 变更模拟。

---

## 一、解决什么问题（第一性原理）

数据平台一旦有了多层加工（源库 → 同步 → 清洗 → 汇总 → 对象/报表），就会遇到三个绕不开的问题，而它们本质上是**同一张依赖图**的三种读法：

1. **影响分析（正向，改动前）**：我要改上游某张表的 schema / 某段 transform，谁会受影响？哪些下游报表、对象、应用会跟着坏？没有血缘图，这只能靠人脑记忆，规模一大必漏。
2. **调试溯源（反向，故障后）**：下游某个数值异常了，它是从哪个上游节点、哪一次 build 引入的？沿依赖边反向遍历即可定位。
3. **合规 / Provenance（来源可追溯）**：监管要求"这个数从哪来、经过哪些加工"，血缘图就是完整来源链。

**第一性原理的关键洞察**：这张图不该靠人手工埋点维护——手工维护的血缘永远滞后、永远不全。正确做法是让它成为 **transform 声明输入/输出的副产品**：既然每段加工都要声明"我读哪些表、写哪张表"（否则调度框架排不了 DAG），那把这些声明累积起来，就天然是一张端到端血缘图。**血缘是构建过程的副产品，不是额外工程**——这是 Foundry 的核心思想，也是我们复刻的主线。

在此之上还有一层更硬的价值：**安全标签随血缘传播**。敏感数据（如 PII）打上标签后，凡是从它派生的下游自动继承该标签，除非在加工中显式声明"我已清洗掉，摘除此标签"。这把血缘从"给人看的图"升级成了"安全策略的执行路径"。

---

## 二、Palantir 怎么做（机制）

Foundry 的血缘实装由**两根轴**构成，落地时必须分开对待，否则会混淆：

- **轴 A：图血缘（graph lineage）**——数据集/节点级别的有向依赖图。
- **轴 B：安全随血缘传播**——真正沿血缘"流动"的是 **Marking（强制访问标签）**，不是"列到列的字段推导"。

> ⚠️ **一个必须先澄清的常见误解**：Foundry 的血缘图**本身是数据集级（node-level）的，不是列到列（column-to-column）的字段推导图**。官方所谓 "column-level" 指的是另外两件事：① Data Lineage 里的**列检索**（判断"哪些数据集含某列"，是列的**存在性**，不是"输出列 C 由输入列 A+B 算出"的推导链）；② Ontology / 数据集上的 **property / cell 级安全 Marking**（PII 等标签精确到属性/单元，且沿血缘继承）。真正的字段级推导血缘 Foundry 图里并不提供（见"Open questions"）。

### A. 图血缘：端到端血缘图（节点 / 边 / 自动生成）

**节点类型**（Graph elements）：
- `Dataset`（数据集）
- `Transform`（= job spec，转换逻辑节点）
- `Schedule`（调度）
- `Artifact`（版本化产物）
- `Ontology 实体`（对象类型 / 链接类型）
- 外部 `Source / Sync`（数据连接）

**边**：有向的"数据依赖"——上游 → 下游，表示"谁喂谁"。

**如何从 transform 自动生成**：因为 **sync 产物与 transform 的输入/输出都是同一个 `Dataset` 抽象**，每次 build 时框架天然知道"此 Dataset 由哪些上游 Dataset + 哪段 transform 生成"，把这些边累积起来就是端到端图。在 Python transform 里，`@transform` 装饰器 + `Input("/path")` / `Output("/path")` 声明**就是**登记依赖给构建框架的动作——同一套声明既用来排 DAG，又用来生成血缘。**不手工埋点。**

**消费者看到的界面形态（Data Lineage app 交互）**：
- **Expand（展开）**：选中节点 → 点 Expand → 用 chevron 选展开层数，或用 double-chevron 一路展开到 raw 源；暴露 ancestors（上游）/ descendants（下游）。
- **Find（查找）**：按节点名或**列名**搜图内节点。
- **Drag select（框选）**：框选多个节点。
- **Histogram of selection properties → Frequent Columns**（右侧面板）：列出选区中最频繁的列名；勾选一/多列，图上就高亮所有含该列的资源——这是**列存在性检索**（跨数据集找列），不是字段级推导血缘。
- **Save / Open graph / 生成只读分享链接**。
- **Branching data lineage**：按分支查看血缘。
- **节点详情 tab**：logs / files / metadata / schema / **job specifications**（可看"这版由哪次 build、哪个输入版本算出"）；dataset preview + logic。

**Node coloring（节点着色，右上角 "Node color options" 下拉）—— 6 值枚举**（对抗验证更正：原研究漏了默认模式，实为 6 种而非 5 种）：
1. **Resource overview**（**默认模式**，按资源类型着色，右上角有 legend 区分 Dataset / Artifact / Writeback Dataset 等）
2. **Build Status**：显示每个资源构建状态；running 的数据集有 open transaction（用于诊断卡住）。
3. **Build Duration**：各数据集构建耗时。
4. **Out-of-date（Staleness）**：哪些 job spec 被判 stale / 过期。
5. **Permissions**：着色指示用户对各数据集 / artifact 的可见权限（配 Check resource permissions）。
6. **Marking Changes**：**仅在 simulation 模式下**作为着色维度出现（见 C 节），非常规下拉项。

> 实装提示：若代码里要枚举着色模式，应写 **6 值**，不要写死 5 值。

**Build / 回滚（可在图上直接操作）**：Build datasets（可选"选中 + 全部 out-of-date 上游"策略；默认只建过期上游，可强制重建最新的）；Manage schedules；Roll back a pipeline / Roll back a dataset。

### B. 安全随血缘传播（核心）

这是"安全跟着数据走"的机制，也是我们栈**最缺的一块**。

**Marking = 强制控制（mandatory control）**：为文件 / 文件夹 / Project 提供额外的访问层，定义资格条件。访问是**二元的**——不满足全部 Marking 条件则**完全不可访问**；多个 Marking 之间是**合取（AND）**语义。它与 discretionary 角色（只能扩权、不能集中限权）相对。核心特征：**Markings travel with the data**——标签跟着数据走，而不是按数据存放位置决定。

> 强制层是**否决式**的：即便 Project Owner 想通过分享把数据给某人，只要那人不满足 Marking 条件，也**保证永远无法访问**（官方原文："guaranteed to never be able to access that data, even if the project owner tries sharing it with them"）。

**两条继承路径**（Marking 沿血缘传播的两个来源）：
1. **文件层级**——Project / 文件夹上有 Marking，其内一切资源继承。
2. **直接数据依赖**——某数据集有 file marking，则依赖它的每个下游数据集继承；这种沿依赖继承来的标签称 **data marking**。且会 "propagate through transform and analysis logic"（穿过转换与分析逻辑传播）。saved 后**立即应用、立即向下游传播**。

**摘除传播（transform 属性，Python API）**：当加工确实清洗掉了敏感数据（如脱敏了 PII），可以在 transform 里显式声明"从这个输入停止向下传播某标签"：

```python
from transforms.api import transform, Input, Output, Markings, OrgMarkings

@transform(
    out=Output("/mfg/clean/workshop_cost"),
    salary=Input(
        "/mfg/raw/worker_salary",
        # ⚠️ 对抗验证更正：Markings / OrgMarkings 是【两个必填位置参数】
        #    (marking_ids, on_branches)，第二个是"应用摘除的受保护分支列表"
        stop_propagating=Markings(["<marking_id>"], ["<protected_branch>"]),   # 摘 PII 传播
        stop_requiring=OrgMarkings(["<org_id>"], ["<protected_branch>"]),      # 摘继承的 Org
    ),
)
def compute(salary):
    ...
```

- `Input.stop_propagating: Markings(marking_ids, on_branches)` —— 停止从该输入向下传播指定 Marking。
- `Input.stop_requiring: OrgMarkings(marking_ids, on_branches)` —— 摘除继承的 Organization（Org 是**特殊类别的 Marking**，故关键字叫 `OrgMarkings`）。
- **约束**（对抗验证逐字确认）：官方原文 "for every removal, you must also specify the protected branches to which the removal should apply"——**每次摘除都必须同时指定受保护分支**（原研究顶部代码块漏了这个实参，照抄会报错 / 不生效）。此外，`stop_propagating` 仅在**受保护分支且开启 "Require security approvals before merging"** 时才生效；且**你无法摘除某继承 Marking，直到你的分支被合并进受保护分支**。

**列 / 单元级安全（真正的 "column-level"）**：
- **Property security policy（属性安全策略）**：与 object security policy 同构，但只作用于**选定的属性子集**，从而实现 **column-level security**（例如 Name / Address / Phone 仅对有 PII marking 的用户可见）。可见性判定分两层：对象实例是否可见由 **object policy** 决定，某属性值是否可见由 **property policy** 决定。二者组合即 **cell-level security**（行 × 列）：不过 object policy → 整行不可见；过了 object policy 但不过 property policy → 该属性值显示 **null**。默认情况下，object security policy **继承其数据源的全部 mandatory controls**（markings / organizations / classifications），可增删。
- **Mandatory Control property（OSv2 专属）**：把对象类型的某个属性的 base type 设为 **Mandatory Control**，映射到 restricted view 上的 marking 列，配 **Allowed markings / Allowed organizations / Max classification**；该属性必须是 required 的；可以"用一个属性来限制同 datasource 内所有其他属性"。materialize（物化）时，物化数据集也要求满足这些控制。这就是把血缘上的 marking **精确落到属性 / 单元**的手段。

**CBAC（Classification-Based Access Controls，政府向）**：基于分类标签（密级）的访问控制。特征：**层级式**——用户只能访问 ≤ 自身密级的数据；支持**析取（disjunctive）**成分来定义 releasability（跨组织 / 国家，如"国 A **OR** 国 B 可发布"，而标准 marking 只支持合取 AND）；**非默认开启，需 Palantir 介入配置**。
> 对抗验证更正（措辞收窄）：原研究称"分类不能与 marking / organization 同挂一个 mandatory control property"。官方 CBAC 页明确 CBAC **可以**与其他访问要求（discretionary 角色、mandatory markings）**在同一资源上并存并取 AND**，但**未**逐字声明"同一个 mandatory control property 上不可混挂"。准确表述应弱化为：**分类作为一个独立的 mandatory control 维度来配置；一个 mandatory control property 承载单一控制类型**——这是 property 的配置约束，而非 CBAC 概念层的禁令。

**Restricted View（受限视图）**：行 / 列级权限的**只读**视图。**故意不能作为 transform 的输入**（官方逐字确认 "cannot be used as an input for transforms"，根因是"行级权限无法在批管道中保持一致"）。它的 provenance 会从后端 Dataset + 对象类型双向携带（含 mandatory control 类属性 Allowed markings / Allowed organizations / Max classification），让分类 / 密级跟着数据走。
> 对抗验证补正：RV "不可导出 / sync" 这半句在概念页**未逐字出现**，属合理推论——官方逻辑是：唯有 materialize（需较高权限、物化后不再带 RV policy）才能把 RV 转成常规 dataset 供下游 / 导出，间接印证 RV 本身不能直接喂 transform / 导出。

### C. 三大用途 + Marking 变更模拟

同一张血缘图承载三种运行时能力：
- **影响分析**（正向）：改上游会影响哪些下游 App / 对象 / 报表（Code Repos 里也有 "Analyze the impact of changes"）。
- **调试**（反向）：溯源异常由哪个上游节点 / 哪次 build 引入。
- **合规 / provenance**：完整来源链满足"数据来源可追溯"。

其中影响分析含一项独有能力 —— **Marking 变更模拟（See the impact of marking changes）**：改标签**之前**先预演爆炸半径。操作路径：在 Access information 侧栏开 **"Simulate access requirements"** toggle → 选数据集 → **Edit markings** → 搜 Marking 勾 / 去勾 → **"Simulate changes"**。图着色按 **4 状态**枚举：
- `Simulate changes applied`（你改的节点）
- `Access affected`（改前后 Marking 不同、访问受影响的数据集）
- `Access unaffected`（改前后相同）
- `No visible transactions`（未构建过或无权看事务）

可切换 simulation 开关而不丢改动。
> 对抗验证补充两条官方限制：① 模拟依赖**最近一次 build**；② **通过 lineage 或父 Project 继承而来的 Marking，其移除无法被模拟**。

---

## 三、模型 / 细节（硬细节照留）

### 节点 / 边模型
- **节点**：`Dataset` / `Transform`(job spec) / `Schedule` / `Artifact` / `Ontology 实体` / `Source-Sync`。
- **边**：有向"数据依赖"（上游 → 下游）。

### 列级血缘的表示（Foundry 实际做法）
Foundry **没有**字段级推导血缘。它的"列级"= 两件独立的事：
1. **列存在性检索**：`Find` 按列名搜 + `Histogram of selection properties → Frequent Columns` 勾列高亮含该列的资源。
2. **property / cell 级安全 marking**：见上文 B 节。

### transform 安全属性（Python，`transforms.api`）
- `Markings(marking_ids, on_branches)`、`OrgMarkings(marking_ids, on_branches)` —— **两个必填位置参数**。
- `Input.stop_propagating: Markings`（optional）、`Input.stop_requiring: OrgMarkings`（optional）。
- 生效前提：分支受保护 + "Require security approvals before merging" 开启；且分支须已合并进受保护分支才能摘除继承 Marking。

### Create Marking API（admin v2）请求体
| 字段 | 类型 | 必填 |
|---|---|---|
| `name` | string | 是 |
| `description` | string | 否 |
| `categoryId` | string（UUID；Org 类为字面量 `"Organization"`） | 是 |
| `initialMembers` | list&lt;PrincipalId&gt; | 否 |
| `initialRoleAssignments` | list&lt;MarkingRoleUpdate&gt;（至少 1 个 ADMINISTER） | 否 |

响应 Marking 对象字段：`id`、`categoryId`、`name`、`description`、`organization`（RID `ri.multipass..organization.<UUID>`）、`createdTime`（ISO8601）、`createdBy`。
- **Remove Markings** 端点：需资源 **RID**（路径参数）+ OAuth scope `api:filesystem-write`。
- 权限区分（对抗验证澄清）：**Apply marking** 权限能贴标签，但不等于成为该 marking 的成员；**移除 marking** 由具名的 **"Remove marking"** 权限门控（移除任一 marking 属于一次 "expand access" 事件），而具名的 **"Expand access"** 权限**专指组织（Organization）维度**的加 / 减——二者不可混为一谈。默认 **Owner role 本身即赋予改 marking 的资源侧能力**（仍须叠加 marking 专属的 apply / remove 权限）。

### Marking 变更模拟状态枚举（4 值）
`Simulate changes applied` / `Access affected` / `Access unaffected` / `No visible transactions`

### Node coloring 模式枚举（6 值）
`Resource overview`（默认）/ `Build Status` / `Build Duration` / `Out-of-date`（staleness）/ `Permissions` / `Marking Changes`（仅模拟态）

### Mandatory Control property（OSv2）配置项
属性 base type = `Mandatory Control`，值为 marking / org ID 的 STRING ARRAY，必须 required；映射到 restricted view 的 marking 列，设 `Allowed markings` / `Allowed organizations` / `Max classification`；MDO 中每个 datasource 各配一个。

### CBAC 特性
层级密级（≤ 自身可见）+ disjunctive releasability（析取 OR）；作为独立 mandatory control 维度配置；非默认开启，需 Palantir 配置。

---

## 四、映射到DataSteward 栈（我们怎么复刻）

**目标**：复刻"图血缘（节点 / 边自动生成）+ Marking 沿血缘传播 + 列 / 单元级安全 + 影响分析 / 模拟"。
**最大杠杆**：**Neo4j 是血缘图的天然载体，我们已有它**（S3 知识图谱已上 Neo4j + graph_query）。

### 1. 图血缘存 Neo4j（复刻 A）
- **节点标签**：`:Dataset`（StarRocks 表 / DuckDB 表）、`:Source`（PostgreSQL 表）、`:Transform`（Flink CDC 作业 / SQL 转换 / dm-load 步骤）、`:Schedule`、`:OntologyType`（已有 KG 对象）。
- **边**：`(:Source)-[:SYNC]->(:Dataset)`、`(:Dataset)-[:DERIVES {transform_rid}]->(:Dataset)`、`(:Transform)-[:PRODUCES]->` / `[:CONSUMES]-`。
- **自动生成（不手工埋点）**：
  - ① 从 `schema.py`（19 表 single source of truth）+ `gen_flink_cdc_sql.py` 解析出 source → sink 映射，生成 `SYNC` / `DERIVES` 边；
  - ② **`pipeline/lineage.py` 从 transform 注册表登记**：dm-load 每步建表时按"读了哪些表 / 写了哪个表"登记 `DERIVES`（等价 `@transform` 的 Input / Output 声明）。把血缘做成 dm-load 的**副产品**——这正是 Foundry 的核心思想。**表级起步 → 列级演进**（列级留待字段映射方案成熟）。
  - FK 骨架：`schema.py` 里已有的外键关系可作为初始 `DERIVES` 边的补充来源。
- **影响分析 = Cypher 变向遍历**：下游 `MATCH (d:Dataset {name:$x})-[:DERIVES*]->(down) RETURN down`；调试上溯把 `*` 方向反过来。

### 2. Marking 沿血缘传播（复刻 B —— 我们最缺的一块）
- **打标签**：在 schema 元数据给列打 `marking`（枚举 `PII` / `SENSITIVE` / `INTERNAL` / `ORG:<x>`，对齐 Foundry Marking 的合取语义）。落 Neo4j：`(:Column {name, marking})` 或 `(:Dataset)-[:HAS_MARKING]->(:Marking)`。
- **传播规则引擎**（复刻"沿数据依赖继承 data marking"）：一条 Cypher / 批作业——凡 `(:Dataset)-[:DERIVES]->(down)`，down 自动继承上游 Marking，**除非该 `DERIVES` 边标了 `stop_propagating=[marking]`**（复刻 transform 摘除属性）。用图显式传播，比 Foundry 的隐式继承**更透明可查**。
- **执行点（把血缘升级成安全策略执行路径）**：**只读 MCP 连接器在查询前做 marking 检查**——调用方 session 若无对应 marking 权限，则拒绝 / 脱敏该列，拒绝事件写 JSONL 审计（我们已有审计骨架，正好承载"谁因缺 X marking 被拒"）。这就把本仓"session_id 关联 audit_log 与 agent_session"的骨架接上了安全语义。

### 3. 列 / 单元级安全（复刻 property / cell security）
- **column-level 在 MCP 连接器层实现**：结果集按 session marking 逐列脱敏（Name / Phone → `****`，除非持有 PII marking）。
- **row-level** 用 PostgreSQL RLS / StarRocks 视图。
- **等价 Restricted View 的"只读、不入转换"约束**：脱敏视图**不作为下游 Flink 输入**——需在连接器层加护栏（Foundry 靠平台强制，我们要自建检查，防止脱敏视图被误当 Flink 源而破坏一致性）。

### 4. 影响分析 + Marking 模拟（复刻 C，落治理台 Streamlit）
- **血缘 tab**：治理台"知识图谱页"已有 → 加**血缘 tab**，用 pyvis / streamlit-agraph 画 Neo4j 血缘图；节点着色下拉复刻枚举（Resource overview / Build Status / Out-of-date / Permissions / **Marking**）。呼应本仓约定"管理平台是调试工具"（CONTRIBUTING.md）：从 session_id 回放任务链 → 跳到血缘图定位失败节点。
- **Marking 变更模拟**：治理台选节点 → "模拟加 PII" → 跑传播 Cypher（**不落库**）→ 图上按 4 状态着色（changes applied / access affected / unaffected / no data），复刻 Foundry simulation。这是**高性价比、可 eval 的杀手锏**。
- **列检索**：治理台搜列名 → Cypher 查 `:Column {name}` 高亮含该列的数据集（复刻 Frequent Columns 的列存在性检索）。

### 5. 与 CDC 血缘对齐
- Flink CDC 的 WAL LSN = Foundry 的高水位游标；每个 CDC 作业在 Neo4j 记一个 `:Transform` 节点，把 replication_slot 状态挂上去做 freshness 着色（复刻 Out-of-date / staleness）。

### eval 建议（呼应"验收必须可量化"）
1. **血缘图真值**：给定表，用 SQL 算出真实上下游，与 Neo4j 图遍历结果比对。
2. **marking 传播真值**：在源表标 PII，断言下游 N 张表全部继承。
3. **拒绝测试**：无 PII marking 的 session 查含 PII 列，必被脱敏 / 拒绝并留审计。

---

## 五、Open questions

1. **列到列（column-to-column）推导血缘**：Foundry 图血缘是**数据集级**，官方 "column-level" 实为列存在性检索 + property / cell 安全，**并非**"输出列 C 由输入列 A+B 算出"的字段级推导图。若我们要真字段级血缘（合规常要求），需自建：解析 Flink / dbt SQL 的 SELECT 表达式抽 column mapping（可借 **sqlglot / OpenLineage column-lineage facet**），Foundry 文档未给此层实装细节，需实测 OpenLineage 方案。
2. **Marking 传播的底层数据结构 / 增量重算**：官方未公开 marking 继承在后端如何存与增量重算（每次 build 全量重推 vs 增量）。我们用 Neo4j 批 Cypher 传播是否需增量、性能阈值（19 表小，未来放大后）待实测。
3. **`stop_propagating` 生效的审批工作流**：官方要求"受保护分支 + 合并前安全审批"，但我们没有 Foundry 的分支 / PR-on-data 机制；在我们栈这个"审批门禁"落在哪（GitHub PR？治理台人工确认？）需决策。
4. **CBAC 层级密级**：是否需要给本平台做密级层级（≤ 自身可见）+ 析取 releasability？官方需 Palantir 介入配置，我们若要做需自定枚举与判定逻辑，属"愿景"而非"今天切片"。
5. **模拟态性能与真值边界**：Marking 变更模拟在大图上的交互延迟，以及 "access affected" 判定的边界（间接依赖多跳后是否仍算 affected）官方未量化，需实测。注意官方两条已知限制——模拟依赖最近一次 build、继承来的 Marking 移除无法被模拟——我们的图传播实现要么规避、要么显式告知用户。
6. **Restricted View "不可入转换" 是否强制**：若治理台脱敏视图被误当 Flink 源会破坏一致性；官方靠平台强制，我们需在连接器层自建护栏检查。
7. **provenance 双来源合并规则**：Foundry 物化对象同时带 Dataset + 对象类型 provenance；我们 Neo4j 里对象节点如何合并两侧 marking（取并集？冲突时取严？）需定规则——倾向"取严"（更严格的 marking 胜出，符合强制控制的否决式语义）。

---

## 六、来源

**Data Lineage（图血缘）**
- https://www.palantir.com/docs/foundry/data-lineage/overview
- https://www.palantir.com/docs/foundry/data-lineage/explore-lineage
- https://www.palantir.com/docs/foundry/data-lineage/find-column
- https://www.palantir.com/docs/foundry/data-lineage/node-coloring
- https://www.palantir.com/docs/foundry/data-lineage/elements-reference
- https://www.palantir.com/docs/foundry/data-lineage/see-impact-marking-changes
- https://www.palantir.com/docs/foundry/data-lineage/check-permissions
- https://www.palantir.com/docs/foundry/data-lineage/stale-datasets
- https://www.palantir.com/docs/foundry/data-lineage/build-datasets
- https://www.palantir.com/docs/foundry/data-lineage/save-share-graph
- https://www.palantir.com/docs/foundry/data-lineage/faq
- https://www.palantir.com/docs/foundry/code-repositories/analyze-impact

**Security / Markings（安全随血缘传播）**
- https://www.palantir.com/docs/foundry/security/markings
- https://www.palantir.com/docs/foundry/security/overview
- https://www.palantir.com/docs/foundry/security/protecting-sensitive-data
- https://www.palantir.com/docs/foundry/security/classification-based-access-controls
- https://www.palantir.com/docs/foundry/security/property-security-markings
- https://www.palantir.com/docs/foundry/security/restricted-views
- https://www.palantir.com/docs/foundry/building-pipelines/remove-inherited-markings
- https://www.palantir.com/docs/foundry/building-pipelines/remove-markings
- https://www.palantir.com/docs/foundry/platform-security-management/manage-markings
- https://www.palantir.com/docs/foundry/platform-security-management/manage-restricted-views
- https://www.palantir.com/docs/foundry/platform-security-management/manage-granular-policies

**Ontology / 对象与属性权限（列 / 单元级安全）**
- https://www.palantir.com/docs/foundry/object-permissioning/object-security-policies
- https://www.palantir.com/docs/foundry/object-permissioning/object-and-property-policies
- https://www.palantir.com/docs/foundry/object-link-types/mandatory-control-properties
- https://www.palantir.com/docs/foundry/object-edits/materializations

**Transforms API（摘除传播）**
- https://www.palantir.com/docs/foundry/transforms-python/transforms-python-api-classes
- https://www.palantir.com/docs/foundry/api-reference/transforms-python-library

**API 参考（Marking / Organization）**
- https://www.palantir.com/docs/foundry/api/v2/admin-v2-resources/markings/create-marking
- https://www.palantir.com/docs/foundry/api/v2/filesystem-v2-resources/resources/remove-markings
- https://www.palantir.com/docs/foundry/api/v2/admin-v2-resources/organizations/organization-basics

> 本文档已吸收对抗验证（`_verifications.md` → "verify: lineage"）的更正：① Node coloring 补入默认模式 Resource overview（6 值枚举）；② `Markings` / `OrgMarkings` 补入必填的 `on_branches` 分支实参；③ Org 为特殊 Marking（确认无误）；④ CBAC "同挂一属性" 措辞收窄为 mandatory control property 配置约束；⑤ Restricted View "不可导出 / sync" 标注为合理推论而非原文；⑥ Marking 模拟补入"依赖最近一次 build""继承来的 Marking 移除无法模拟"两条限制。
