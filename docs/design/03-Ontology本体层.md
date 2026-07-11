# 03 · Ontology 本体层

> **一句话定位**：Ontology 是"决策中心的数字孪生"——把散落在数据集里的表提升为业务能读懂的**对象（名词）+ 动作（动词）**，让人和智能体在同一个受治理的语义模型上做决策并把结果写回源系统。它对应我们平台里**数仓（StarRocks）之上、智能体与治理台之下**的语义层，是"知识图谱页"的下一站升级。

---

## 一、解决什么问题（第一性原理）

数据集（dataset）是**行列的物理容器**：它知道"有一张 `sales_order` 表，里面有 10 万行、若干列"，但它不知道"这一行是一张**销售订单**、它**属于**某个客户、它**需要**某个物料 265 件、它现在**能不能发货**"。这三个"不知道"正是决策所需的全部——而数据集一个都答不上来。

在数据集之上再加一层语义（Ontology），本质是要补齐四件数据集天生缺失的东西：

1. **语义（这是什么）**：把 `sales_order` 这张表**提升为**"销售订单"这个**对象类型（Object Type）**，把 `qty_required` 这一列**提升为**带单位、带约束、可搜索的**属性（Property）**。名词从此有了业务身份，而不只是列名。
2. **关系（和谁有关）**：把外键、join 表、文档里抽出来的隐含关联，**显式声明为链接类型（Link Type）**。于是"订单 → 客户""订单 → 所需物料 → 供应商"变成可沿着走的路径，而不是每次都靠 SQL join 现拼。
3. **动作（能做什么 + 能不能做）**：把"确认发货""调整安全库存"这类业务操作，编码为**动作类型（Action Type）**——一次**事务式编辑**，带**提交条件（能不能做，如"库存 ≥ 需求"）\*\*和**副作用（做完通知谁、回写哪里）**。数据层从此不再只读，而是决策的落点。
4. **闭环（改完写回哪）**：动作提交后，最新态落到该对象类型的**写回数据集（writeback dataset）**，再经副作用把变更**推回 ERP/MES 源系统**——决策不再停在看板上，而是回到业务系统里生效。

一句话：**数据集回答"有什么数据"，Ontology 回答"这是什么、和谁有关、能对它做什么、做完写回哪"**。前者面向存储，后者面向决策。这也是 Ontology 相对"只读语义层 / 只读知识图谱"的根本差异——**名词 + 动词 + 写回 + 动态安全同处一个受治理系统**。

Palantir 把 Ontology 的五个构件分成两层：

| 层 | 构件 | 角色 |
|---|---|---|
| **语义层（名词）** | Object Type / Property / Link Type | 描述"世界长什么样" |
| **动力学层（动词）** | Action Type / Function（+ Dynamic Security） | 描述"能对世界做什么" |

---

## 二、Palantir 怎么做（机制）

### 2.1 Object Type 对象类型：一张表提升为一个对象类型

创建一个对象类型时，**必填**字段：

- **ID**：小写字母/数字/连字符，字母开头。
- **Display name**（显示名）/ **Plural display name**（复数显示名）。
- **API name**：PascalCase，1–100 字符，经 NFKC 规范化，非保留字。
- **Backing datasource**（背书数据源）：这个对象类型的数据从哪来。
- **Primary key property**（主键属性）。
- **Title key property**（标题属性，即展示时用哪个属性当"名字"）。

**选填**字段：Description、Icon、Color、Groups（分类标签）、Aliases（搜索同义词）。

**硬规则（务必记住）**：

> "A single datasource can only be used to back one object type."（**一个数据源只能背书一个对象类型**——1 datasource ↔ 1 object type。）

**主键要求**：在背书数据源内必须**唯一 + 确定性（deterministic）**——即跨构建（rebuild）保持稳定，否则用户对该对象所做的编辑会在重建时丢失；因此主键**必须基于列值**，不能用随机数或自增序列。

两个枚举：

- **状态（status）**：`ACTIVE` / `ENDORSED` / `EXPERIMENTAL` / `DEPRECATED`。
- **可见性（visibility）**：`NORMAL` / `PROMINENT` / `HIDDEN`。

### 2.2 Property 属性：列提升为强类型属性

每个属性可配置：ID、Display name、Description、API name（camelCase，1–100）、**Base type**、Keys（是否为 title / primary key）、Status（active / experimental / deprecated）、Visibility（prominent / normal / hidden）、Value formatting（数值 / 日期时间 / user id / resource id 的格式）、Conditional formatting（条件渲染规则）、Type classes（供应用解释的附加元数据）、Render hints、Searchable flag（可搜索）、Sortable flag（可排序）、RID（自动生成）。

每个属性**创建时必填**：Property ID / Display name / **Backing column mapping**（映射到背书数据源的哪一列）/ API name（camelCase，1–100）。

**Base type 完整枚举**（官方 base-types 页）：

- **标量**：String、Integer、Long、Short、Byte、Float、Double、Decimal、Boolean、Date、Timestamp。
- **特殊**：Vector（语义搜索用）、Geopoint、Geoshape、Attachment（文件）、Time series、Media reference、Cipher text（Cipher 加密串）、Struct（多字段模式）。
- **数组**：除 **Vector** 与 **Time series** 外，所有 base type 均可作数组；"All field types are valid base types **except for Map and Binary types**"（Map / Binary 不能作 base type）；OSv2 数组**不允许 null 元素**。

### 2.3 Value Type 值类型：base type 之上的语义包装 + 约束

Value Type 是在 base type 之上的**语义包装 + 可复用校验约束**，可跨多个属性复用同一套校验。约束枚举：

| 约束 | 适用类型 | 说明 |
|---|---|---|
| **Enum（one of）** | String / Boolean / Decimal / Double / Float / Integer / Short | 取值只能是枚举之一；字符串可配置区分大小写 |
| **Range** | Decimal / Double / Float / Integer / Short / Date / Timestamp / String（约束长度）/ Array（约束大小） | min / max 上下界 |
| **Regex** | String | 正则匹配 |
| **RID** | — | 必须是资源标识符 |
| **UUID** | String 专属 | 必须是 UUID |
| **Uniqueness** | — | 唯一性 |
| **Nested** | Array 专属 | 嵌套约束 |
| **Element constraints** | Struct 专属 | 对结构体各字段的约束 |

### 2.4 Link Type 链接类型：三种背书方式对应三种基数

链接类型的"怎么背书"直接决定它支持哪种**基数（cardinality）**：

1. **Object type foreign keys（对象类型外键）** → 支持 **one-to-one** 与 **many-to-one**。一侧的**外键属性**指向另一侧的**主键属性**，**无需额外数据集**。
2. **Join table dataset（连接表数据集）** → **many-to-many**。背书数据集须含**两侧主键各一列**（一列只能映射一个主键），可自动生成 join 表。
3. **Backing object type（中间对象类型）** → 用一个中间对象类型 + 两条指向它的 **many-to-one** 链，从而表达 many-to-one 关系。

每一侧的字段：**Display name**（描述"指向该侧"的关系）、**API name**（小写字母开头、字母数字、**同一对象类型内唯一**、1–100、NFKC）。

### 2.5 Action Type 动作：把业务规则编码为一次事务式编辑

一个 Action Type = **一次事务式编辑**。它由五个构件组成：

- **Parameters（参数）**：用户输入。
- **Rules（规则）**：这次动作到底做什么变更。
- **Submission criteria（提交条件）**：满足什么条件才**能提交**。
- **Side effects（副作用）**：提交后额外触发什么。
- **Permissions（权限）**：谁能调用。

**Rules 全列表**（官方 rules 页）：

| 规则 | 说明 |
|---|---|
| Create object | 建对象 |
| Modify object(s) | 改对象 |
| Create or modify object(s) | 建或改对象（upsert） |
| Delete object(s) | 删对象 |
| Create link(s) | 建链接（**仅 many-to-many**） |
| Delete link | 删链接 |
| Function rule | 调用一个 Ontology edit 函数 |
| + 6 个 interface 变体 | Create / Modify / Delete objects of interface；Create / Delete links on objects of interface |

**Submission criteria（提交条件）= conditions + operators**：

- **模板**：`Current User`（检查 user id / 组 / multipass 属性）、`Parameter`。
- **操作符（单值）**：`is` / `is not` / `matches` / `is less than` / `is greater than or equals`。
- **操作符（多值）**：`includes` / `is included in` / `each is` / `each is not`。
- **可引用**：参数值 / 用户属性（id / 组 / 组织）/ 对象属性值 / 静态值。
- **可用 AND / OR / NOT 嵌套**。
- **不支持**：attachment 参数、object set 参数。
- 官方示例：`"Aircraft > Engine Count is greater than or equals 2"`（飞机的引擎数 ≥ 2 才能提交）。

**Action parameter 配置**：约束类型示例有 `"User input"`（用户自由输入）、`"Multiple choice"`（多选，如 P0 / P1 / P2）；可设 default value（可取环境变量如 `"Current object"`）；Display 可设 `"Hidden"`。

**Side effects（副作用）**：

- **Notification**（站内通知）。
- **Webhook**：可配置 pre-edit / post-edit 执行，把变更**写回外部系统**。
- **Schedule**：触发一次构建（build）。

### 2.6 写回机制（writeback）

动作提交后**立即写入 Ontology**：用户编辑的最新对象数据落在该对象类型的 **writeback dataset**（写回数据集）；再经 **Side effect → Webhook** 把变更**推回 ERP / MES 等源系统**。这是"决策回到业务系统生效"的关键一环。

### 2.7 Function 函数：任意复杂逻辑

用 **TypeScript / Python** 编写任意复杂逻辑。**Function-backed Action（函数驱动的动作）**有两种写法：

- **TS v1**：用 `@OntologyEditFunction` 装饰器。
- **TS v2 与 Python**：用 **edits API** 直接 create / modify / delete。

适用场景："改多个关联对象 / 跨对象计算 / 一次建多对象 + 建链"这类单条 Rule 表达不了的逻辑。受**双重限额**约束：action 限额 + function 超时 / 资源限额。

### 2.8 OSv2 存储：读写双引擎 + 自研索引

Ontology System v2（OSv2）的组件：

- **Object Data Funnel**：编排写入（对数据集/虚拟表/流做增量索引）。
- **OMS**：存元数据（schema）。
- **Object Databases**：自研增强索引格式，为 Search-Around（沿链接横跳搜索）与写回优化。
- **OSS（Object Storage Service）**：服务读 / 搜索 / Search-Around。
- **Actions Service**：应用结构化编辑（保证一次改多对象/链的原子提交）。

机制链：`数据集 / 虚拟表 / 流 →（Object Data Funnel 增量索引）→ Object Databases → OSS 读+搜索 / Actions Service 应用编辑`。**读写双引擎**；**Materialization** 用于 schema 破坏性变更后**迁移用户编辑**。

**已知硬限额**：String 属性 ≤ **12 MB**；Array 属性 ≤ **100,000 元素**；数组无 null 元素。
（"单对象类型数百亿对象""单次 action 编辑上限 ~10,000 对象"为**厂商口径**，不作为工程依据。）

### 2.9 OSDK 代码生成

从本体元数据**生成强类型 SDK**：TypeScript（NPM）/ Python（Pip / Conda）/ Java（Maven）/ OpenAPI 绑定。其访问 token **"scoped only to the ontological entities you want your application to access"**（token 按本体实体范围化，最小权限）。

Python OSDK 用法（verbatim）：

```python
# 取单个对象
client.ontology.objects.ExampleRestaurant.get("primaryKey")

# 迭代
list(client.ontology.objects.ExampleRestaurant.iterate())

# 分页
result = client.ontology.objects.ExampleRestaurant.page(page_size=30, page_token=None)
result.next_page_token
result.data

# 过滤 + 排序（~ 取非，& 为 AND，| 为 OR）
client.ontology.objects.ExampleRestaurant \
    .where(~ExampleRestaurant.object_type.restaurant_name.is_null()) \
    .order_by(ExampleRestaurant.object_type.restaurant_name.asc()) \
    .iterate()

# 聚合
client.ontology.objects.ExampleRestaurant.count().compute()
client.ontology.objects.ExampleRestaurant.avg(
    ExampleRestaurant.object_type.number_of_reviews
).compute()

# 链遍历：V2 中 .take / .where / .group_by 也可作用于 link
```

### 2.10 链接基数速查

| 背书方式 | 支持基数 | 需要额外数据集？ |
|---|---|---|
| Object type foreign keys | one-to-one、many-to-one | 否（外键属性 → 对方主键属性） |
| Join table dataset | many-to-many | 是（含两侧主键各一列） |
| Backing object type | many-to-one | 是（中间对象类型 + 两条 many-to-one 链） |

---

## 三、Schema / 定义示例

### 3.1 一个完整 Object Type 定义（官方 Get Object Type V1 JSON，verbatim）

```json
{
  "apiName": "employee",
  "description": "A full-time or part-time employee of our firm",
  "primaryKey": ["employeeId"],
  "properties": {
    "employeeId": { "baseType": "Integer" },
    "fullName":   { "baseType": "String" },
    "office":     { "description": "The unique ID of the employee's primary assigned office", "baseType": "String" },
    "startDate":  { "description": "The date the employee was hired (most recently, if they were re-hired)", "baseType": "Date" }
  },
  "rid": "ri.ontology.main.object-type.0381eda6-69bb-4cb7-8ba0-c6158e094a04"
}
```

> **V1 vs V2 差异**：V1 用扁平的 `"baseType"`；V2 的 `ObjectTypeV2` 用嵌套的 `dataType.type`，并多出 `displayName` / `pluralDisplayName` / `status`（`ACTIVE|ENDORSED|EXPERIMENTAL|DEPRECATED`）/ `titleProperty` / `visibility`（`NORMAL|PROMINENT|HIDDEN`）/ `icon`（BlueprintIcon）/ `aliases` / `datasources` 字段。V2 的 `properties` 值为 `PropertyV2 { dataType, description, rid }`。

### 3.2 一个对象类型的属性 / 链接 / Action 清单（示意）

以官方示例中反复出现的 `Aircraft`（飞机）对象类型为例，展示"一个对象类型完整长什么样"：

**属性（Property）列表**（示意）：

| API name | Base type | Keys | 说明 |
|---|---|---|---|
| `aircraftId` | String | primary key | 主键，须唯一 + 确定性 |
| `tailNumber` | String | title key | 标题属性（展示用） |
| `engineCount` | Integer | — | 引擎数（提交条件会用到） |
| `manufacturer` | String | — | 可加 Enum Value Type 约束 |
| `lastServiceDate` | Date | — | — |

**链接（Link Type）列表**（示意）：

| 链接 | 基数 | 背书方式 | 指向 |
|---|---|---|---|
| `operatedByAirline` | many-to-one | Object type foreign key | → `Airline` |
| `assignedFlights` | many-to-many | Join table dataset | ↔ `Flight` |

**Action（Action Type）列表**（示意）：

| Action | Rules | Submission criteria | Side effects |
|---|---|---|---|
| `groundAircraft`（停飞） | Modify object（改状态字段） | `Current User` 属于运控组 | Notification |
| `assignToFlight`（派飞） | Create link（→ Flight，仅 m-n） | `Aircraft > Engine Count is greater than or equals 2` | Webhook（回写排班系统） |

> 说明：这里的属性 / 链接 / Action 三张清单**合起来才是"一个对象类型的完整定义"**——名词的身份（属性）、名词间的关系（链接）、能对名词做的操作（Action）缺一不可。示例结构照官方形态给出，具体字段名为示意。

---

## 四、映射到DataSteward 栈（我们怎么复刻）

目标：在我们的栈（**StarRocks 数仓 / PostgreSQL 源 / Flink CDC / Neo4j 图 / pgvector / 只读 MCP + JSONL 审计 / 无头 Claude / Streamlit 治理台**）上，把五个构件逐一落地。落地点是一个新的 `ontology/` 目录，作为对象注册表的 single source of truth。

### 4.1 Object Type ← 从 `dm/schema.py`（19 表）派生

把 `dm/schema.py` 的 **19 张表升级为"对象类型注册表"**（YAML / JSON 作为 single source of truth）。每个对象类型显式声明：

- `api_name`（PascalCase）、`display_name` / `plural`、`primary_key`、`title_property`；
- `backing_datasource`（StarRocks 视图名 / PG 表名）；
- `status`（active / experimental / deprecated）、`groups`、`aliases`。

落实 Palantir 的 **"1 datasource ↔ 1 object type"**：**每个对象类型绑定一张 StarRocks 视图**。本仓冻结的稳定测试 ID（`M0001` / `SO0001` / `S001`）正好当对象实例主键；强制主键**确定性**——用**业务 ID 而非行号**，避免重建丢编辑。

### 4.2 Property + Value Type ← 每列扩元数据

给每列扩充元数据：`base_type`（映射到我们的类型：String / Integer / Double / Date / Timestamp / Struct / Geoshape…）、`description`、`unit`（单位）、`visibility`、`searchable` / `sortable`、`value_type` 约束（Range / Regex / Enum / UUID）。

**Vector 属性天然对应 pgvector 列**：Palantir 的 Vector base type（语义搜索）与我们的 pgvector 是**同一意图**——可直接把物料 / 文档的嵌入声明为对象的 `vector` 属性，语义检索与结构化查询统一在对象模型里。

### 4.3 Link Type ← FK + join 表 + 文档抽取，物化进 Neo4j

三种基数用现有栈实现：

- **n-1 / 1-1** → StarRocks 外键约定（多侧列 → 一侧主键），对应 Palantir 的 **object type foreign keys**；
- **m-n** → 一张 join 表（如 `material_supplier`），对应 Palantir 的 **join table dataset**；
- 从**文档抽取**出的隐含关联，同样登记为链接（对接知识图谱页已有的抽取能力）。

同时把这些链接**物化进 Neo4j**（节点 = 对象、边 = link type）。Neo4j 天然支持 Palantir 的 **Search-Around（沿链接横跳）**，S3 已经搭好。链接定义写进对象注册表，供智能体做**强类型遍历**。

### 4.4 Action Type + 写回 ← 当前最大缺口（全只读 → 事务写回）

这是当前平台**最大的缺口**（现在全只读）。复刻方案：定义 **action 注册表**（`parameters` + `rules` + `submission_criteria` + `side_effects` + `permissions`），每个 action 是一次事务。

**最小可行 Action = "确认发货 `shipOrder`"**：

- **parameters**：`order_id`、`qty`；
- **submission_criteria**：用我们的操作符实现 `stock >= demand`（对应官方 `is greater than or equals`）；
- **rules**：`Modify object`（库存 −）+ `Create link`（order → shipment）；
- **写回**：落一张 **writeback 表**（与只读 `warehouse` 分离，正好延续我们"warehouse 只读 + logs 追加"的读写分离哲学）；
- **side_effect**：钉钉推送（≈ Notification）+ 可选 Webhook 回写 PG 源；
- **审计**：全程写 JSONL（谁 / 何时 / 改了什么）。

回写 PG 源后由 **Flink CDC** 传导回 StarRocks，形成**决策闭环**。

### 4.5 Function ← 抽出业务逻辑函数层

把散在各处的业务逻辑（如**可发量计算**、**缺料判断**）抽成一个 Python **函数层**：既供 MCP 工具调用，也供 action 驱动（≈ function-backed action）。同一份逻辑，只读查询和写回动作共用。

### 4.6 OSDK-lite ← 从对象注册表生成 MCP 工具 schema + Python 客户端

我们的"强类型 SDK" = 从**对象注册表生成 MCP 工具 schema**：现有 3 个只读工具 → 增加带 `submission_criteria` 校验的**写工具**；并可生成 Python 客户端方法（`list` / `get` / `where` / `traverse`）给智能体。token / 权限**按对象类型范围化**（对齐 OSDK 的最小权限 token）。

### 4.7 Dynamic Security ← 审计从"事后留痕"前置为"准入控制"

把 `audit_log.jsonl` 从**事后留痕**前置为**准入控制**：action 提交前按对象属性（如**区域**）做**行级校验**，写进 `submission_criteria` 的 `Current User` 条件。

### 4.8 治理台 ← 对象浏览器（对标 Workshop 对象视图）

Streamlit 治理台已按 `session_id` 回放任务链（≈ Palantir 审计）。下一步加**"对象浏览器"**：列对象类型 → 点开实例 → 显示其链接与**可用 action 按钮**，直接对标 Palantir Workshop 的对象视图。

### 4.9 五构件映射总表

| Palantir 构件 | DataSteward 栈落地 |
|---|---|
| Object Type | `ontology/` 对象注册表，从 `schema.py`(19表) 派生；每个绑定一张 StarRocks 视图 |
| Property + Value Type | 每列扩元数据 + 约束；Vector 属性 → pgvector 列 |
| Link Type | FK（n-1/1-1）+ join 表（m-n）+ 文档抽取；物化进 Neo4j 供 Search-Around |
| Action Type + 写回 | action 注册表；`shipOrder` 最小可行；writeback 表 + 钉钉/Webhook + JSONL 审计；回写 PG → Flink CDC 闭环 |
| Function | Python 函数层（可发量/缺料）；供 MCP 与 action 共用 |
| OSDK | 从注册表生成 MCP 写工具 schema + Python 客户端；权限按对象类型范围化 |
| Dynamic Security | 审计前置为行级准入控制，写进 submission_criteria |

---

## 五、Open questions

1. **属性数 / 对象类型数上限**：调研引"2000 属性"，但官方 data-restrictions 页只明确 String 12 MB / Array 100k 元素，未给属性数 / 对象类型数上限——需实测或查 platform limits 页确认。
2. **厂商口径数字不照搬**："单次 action 编辑 10,000 对象""单对象类型数百亿对象"为厂商口径，未在限额页复现——复刻时以我们 StarRocks / PG 的实际事务能力为准。
3. **确定性主键的工程含义**：Palantir 强调主键须 deterministic，否则重建丢用户编辑。我们用 Flink CDC 增量 + StarRocks 时，需确认对象主键与源 PG 主键一一对应且不随重导变化——这决定 writeback 与源的对齐方式，需实测。
4. **Action 事务原子性**：Palantir Actions Service 保证一次改多对象 / 链原子提交。StarRocks（分析库，事务弱）做写回并不合适——写回目标应是 **PG（OLTP）** 还是单独 writeback 存储？倾向：写回落 PG 源、由 Flink CDC 同步回 StarRocks，可能更贴合，需决策。
5. **Materialization 无对应物**：schema 破坏性变更后迁移用户编辑，在我们栈无对应——PoC 阶段是否需要，还是简单"重导 + 编辑层 join"即可？待定。
6. **Action parameter 完整类型枚举**未抓全（只见 Multiple choice / User input / Object 引用）——需查 parameter 子页或用 API ontologies-v2 的 ActionType schema 补齐，才能 1:1 定义我们的 action 参数模型。
7. **OSDK Action 调用的 Python 语法**（`client.ontology.actions.xxx.apply(...)` 与批处理）本轮未抓到 verbatim——若要照搬"生成写工具"的接口形态需再取。
8. **Value Type 约束的校验时机**（写入时 vs 索引时 vs action 提交时）官方未明确——影响我们把约束放在 MCP 写工具还是 StarRocks 约束层。

---

## 六、来源

- Ontology overview — https://www.palantir.com/docs/foundry/ontology/overview
- Ontology system（架构中心）— https://www.palantir.com/docs/foundry/architecture-center/ontology-system
- Object/Link types — type reference — https://www.palantir.com/docs/foundry/object-link-types/type-reference
- Base types — https://www.palantir.com/docs/foundry/object-link-types/base-types
- Create object type — https://www.palantir.com/docs/foundry/object-link-types/create-object-type
- Property metadata — https://www.palantir.com/docs/foundry/object-link-types/property-metadata
- Properties overview — https://www.palantir.com/docs/foundry/object-link-types/properties-overview
- Structs overview — https://www.palantir.com/docs/foundry/object-link-types/structs-overview
- Value type constraints — https://www.palantir.com/docs/foundry/object-link-types/value-type-constraints
- Link types overview — https://www.palantir.com/docs/foundry/object-link-types/link-types-overview
- Create link type — https://www.palantir.com/docs/foundry/object-link-types/create-link-type
- Action types overview — https://www.palantir.com/docs/foundry/action-types/overview
- Action rules — https://www.palantir.com/docs/foundry/action-types/rules
- Action parameter overview — https://www.palantir.com/docs/foundry/action-types/parameter-overview
- Action getting started — https://www.palantir.com/docs/foundry/action-types/getting-started
- Submission criteria — https://www.palantir.com/docs/foundry/action-types/submission-criteria
- Function-backed actions overview — https://www.palantir.com/docs/foundry/action-types/function-actions-overview
- Object indexing — data restrictions — https://www.palantir.com/docs/foundry/object-indexing/data-restrictions
- API ontologies-v2 — get object type — https://www.palantir.com/docs/foundry/api/ontologies-v2-resources/object-types/get-object-type
- API ontology-resources — get object type — https://www.palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type
- Ontology SDK overview — https://www.palantir.com/docs/foundry/ontology-sdk/overview
- Python OSDK — https://www.palantir.com/docs/foundry/ontology-sdk/python-osdk
- 博客：Connecting AI to decisions with the Palantir Ontology — https://blog.palantir.com/connecting-ai-to-decisions-with-the-palantir-ontology-c73f7b0a1a72
