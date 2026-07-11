# 05 · 权限与 Markings

> **一句话定位**：Palantir 把"谁能看/改哪一行、哪一列、哪一格"做成一套**内嵌在数据本身、工程师改不掉、沿血缘自动传播**的强制层，再叠一层可授予的自主角色层——治理不是外挂的中间件，而是架构本身。
>
> **对应我们平台的哪一层**：这是横切我们全栈的**治理面**，具体落点是**只读 MCP 连接器**（`src/dm/connector/mcp_server.py` 的 `run_sql` 等工具）——它是无头 Claude 智能体读数据的唯一入口，天然是"安全边界的终点"（等价于 Palantir 中 Restricted View 不能作为 transform 输入这一硬约束）。强制门、自主门、行/列/单元格过滤全部在这里对 caller 身份强制执行；写回权限走另一条完全独立的通道。

---

## 一、解决什么问题（第一性原理）

### 1.1 为什么"治理即架构"，而不是"治理即中间件"

传统数据平台的权限做法是"在应用层加一道网关/中间件":BI 前端过滤、API 层校验、或者给每个人配不同的数据库账号。这条路线有三个结构性漏洞:

1. **能绕过**。只要有第二条通路（一个直连数据库的 psql、一个新写的 ETL 作业、一个导出按钮），网关就形同虚设。权限挂在"访问路径"上,而访问路径永远修得出新的。
2. **不传播**。给源表 `customer` 配了"只有采购能看客户联系方式",但工程师把它 `JOIN` 进一张宽表 `dim_customer_360` 之后,这条限制不会自动跟过去——派生表成了脱敏的黑洞。权限挂在"表"上,而数据会流动、会被复制、会被聚合。
3. **owner 能自我提权**。表的属主既能改数据又能改权限,于是"能改权限的人"总能给自己开后门。强制约束和资源属主没有真正解耦。

Palantir 的第一性回答是:**把访问要求做成数据的一个不可分割的属性(Marking),让它沿数据血缘自动并集传播,并放在一个连资源 owner 都无法绕过的强制判定层里**。于是:

- **不能绕过**:强制层是"否决式(deny-overrides)"的——原文 "mandatory controls will always prevent an ineligible user from accessing a resource, **regardless of the user's role**"。无论你从哪条路来、是什么角色,不满足 Marking 就是看不到。
- **自动传播**:Marking "travels with the data"——每一张依赖它的下游数据集都会继承(称 **data marking**),继承规则是取所有输入 marking 的**并集**。工程师做再多 transform 也洗不掉。
- **owner 也绕不过**:即使资源 owner 主动把资源分享给某人,只要那人不满足强制 Marking,依然 "guaranteed to never be able to access that data, even if the project owner tries sharing it with them"。

这就是"治理即架构":权限不是加在数据之上的一层软件,而是数据模型本身的一部分。

### 1.2 为什么要分"强制层"和"自主层"两层

单一权限模型无法同时满足两类互斥的诉求:

- **合规诉求**要求"中央集权、不可下放、否决式":客户 PII、财务数据这类东西,必须由治理团队统一管控,任何业务线负责人都无权决定谁能看。这对应**强制层(Mandatory)**。
- **协作诉求**要求"灵活、可下放、增量式":一个项目负责人要能随手把自己项目的看/改权限分给同事,不必每次都走中央审批。这对应**自主层(Discretionary)**。

Palantir 让两层**用 AND 叠加**:能看一份数据 = 通过强制门 **AND** 通过自主门。强制层负责"绝不该看的绝对看不到"(下限,不可突破),自主层负责"该协作的能灵活协作"(上限,可增量放开)。两层职责正交,各管一头。关键性质:

- 强制层是**否决式**的(deny 优先):有一个不满足就整体拒绝。
- 自主层是**加法式(additive)**的:原文 "discretionary controls can only add permissions for a user and cannot restrict"——角色只能给你加权限,永远不能减。想收紧只能靠强制层。

这个"强制否决 + 自主叠加"的非对称设计,是整套权限体系的地基。

### 1.3 为什么读权限和写权限要拆成两条独立路径

一个反直觉但极重要的设计:**能改一条记录,不代表能看这条记录**。

制造业场景里这非常常见:一个仓管员要对某批物料"确认入库",但这批物料关联的采购价、供应商合同条款他无权查看。若沿用"要改必先能读"的传统假设,就得把敏感字段也放开给他——权限被写操作反向撑大了。

Palantir 把写回(Action)做成**独立于读权限的执行门**:在"仅限 Action 编辑"模式下,用户只要对被编辑对象有 Read 就能提交修改,而无需通过行/列级的可见性过滤——原文 "it is possible for users to create objects that they cannot view"、"users can modify records they cannot independently view"。写路径由 Action 自己的 apply 权限 + submission criteria(提交条件)把关,与读路径彻底解耦。

这样才能表达"你能推动这个业务动作,但你看不到它背后的全部数据"——一种读写不对称的最小授权。

---

## 二、Palantir 怎么做(机制)

### 2.1 两层地基:Mandatory AND Discretionary

读一个资源,须**同时**通过两层,AND 关系:

| 层 | 别名 | 组成 | 治理方式 | 语义 | 传播 |
|---|---|---|---|---|---|
| **Mandatory（强制）** | 强制控制 | Markings + Organizations + Classifications | 中央管理,资源 owner 改不动其成员资格 | **否决式**:不满足即拒,与角色无关 | 沿文件层级 + 数据血缘自动传播 |
| **Discretionary（自主）** | 自主控制 | Roles(RBAC) | 资源 owner 可授予 | **加法式(additive)**:只加不减 | 沿资源树继承 |

术语表原文:
- Marking = "an access requirement applied to resources that restricts access in an **all-or-nothing** fashion"。
- Discretionary Control = "additive, can only add permissions for a user and cannot restrict"。

### 2.2 自主层:Roles(RBAC)

**4 个默认 Role,从强到弱:`Owner` > `Editor` > `Viewer` > `Discoverer`。**

| Role | 能力 | 备注 |
|---|---|---|
| **Owner** | 读 + 写 + 管理权限/分享 + 下载 + (默认)改本资源 Markings | 最高 |
| **Editor** | 读 + 写 + 下载 | |
| **Viewer** | 读 + 下载 | |
| **Discoverer** | 只能看到资源**名字和元数据**,不能读内容、**不能下载** | 用于"应知道它存在、但不该看内容/下载"的场景 |

规则:
- **授权只能授"同级或更低"**:Owner 可授 4 种任意;Discoverer 只能授 Discoverer。防止低权用户提权他人。
- **沿资源树继承**:Project/folder 上授的 Viewer,级联到其中全部资源。通常在 **Project 级**授权以保持一致,可关掉 folder/file 级授权开关。
- **可自定义 Role**:Role = "a collection of permissions that define the specific workflows that a user can perform on a given resource"。可按需裁剪出自定义角色(例如"有较高权限但去掉 download workflow")。
- **管 Role 需 Organization 上的 "Manage roles and role sets" 权限**。注意官方把两件事分述两处:**授予**该权限在 Control Panel → Organization Administrator;**实际管理/自定义** Role 在 Platform Settings → Roles。
- **对象类型 vs 对象实例的可见性不同**(逐字确认):查看**对象类型**只需对本体资源有 View、**不需**对 backing datasource 有 View;查看**对象实例**须 View 对象类型 **AND** 有底层数据访问(由安全策略或 datasource 权限决定)。

> **⚠ 对抗验证更正 1(硬错误)**:旧本体(legacy Ontology)的 Role 是 **4 个**(Ontology Owner / Editor / Viewer / **Discoverer**,Discoverer 只能看资源名与元数据),**不是 3 个**。此旧模型已被 Compass 项目 Role 取代。

### 2.3 强制层核心:Markings

- **二元 all-or-nothing**:有资格 = 全见,无资格 = 全不见,没有中间态。
- **标准 marking 之间合取(boolean AND)**:一份资源同时贴了 `PII` + `FIN`,用户必须**两个 marking 都持有**才能访问——原文 "a user must be a member of **all** the Markings"。
- **组织成 Marking Category**:category = "a collection of Markings",其可见性本身可限定给某些 Organizations。
- **discovery restriction(发现限制)**:无资格的用户**连资源存在都看不到**——搜索、目录里都不出现。这比"看到但打不开"更强。
- **沿两条链自动传播**:
  1. **文件层级**:Project/folder 上贴的 marking,级联到内部全部资源。
  2. **数据依赖**:"every dataset that depends on it inherits that Marking"——每个依赖它的下游数据集自动继承,继承来的称 **data marking**,取所有输入 marking 集合的**并集**。无资格用户可见派生表的元数据,但看不到数据。
- saved 后**立即应用、立即向下游传播**。

> **⚠ 对抗验证更正 2(机制归属,关键)**:关于"放宽/移除 marking 需要什么权限",官方区分两层,不可混为一谈:
> - **移除任一 marking = 一次 "expand-access" 事件**(术语表原文:"In the case of Markings, the removal of any Marking is an expand access event"),由具名的 **"Remove marking"** 权限门控——移除须**同时**具备该 marking 的 **apply + remove** 权限。
> - 而具名的 **"Expand access" 权限实际管的是 Organizations**(加/减组织维度),在 Control Panel → Organization permissions → Marking permissions 授予。
> - 即:**"移除 marking"用 `Remove marking` 权限;"Expand access" 权限专指组织维度**。研究初稿把二者混淆,已更正。

> **⚠ 对抗验证更正 3(措辞收窄)**:"Owner 改不动 marking / 与 Owner role 完全解耦"这一表述偏强。manage-markings 明说:移除 marking 除 marking 专属权限外,还需 "a role that allows you to change its Markings … this access is available with the **Owner** role"。即**默认 Owner role 本身即赋予"改本资源 marking"的资源侧能力**(仍须叠加 marking 专属的 apply/remove 权限才能真正动某个具体 marking)。"解耦"成立之处在于:marking 的成员资格是**中央管理、独立授予**的。但强制层"否决式、Owner 无法通过分享把无资格者放进来"这一核心论断**完全属实**。

### 2.4 CBAC(分类 / 多级安全,政府向)

Classification-Based Access Controls,为政府敏感信息(军规多级密级)设计:

- **默认关闭,需 Palantir 介入配置**(原文 "not enabled by default" / "requires Palantir involvement")。制造业客户大概率用不到。
- 结构:classification 组织成 category,一个 classification 可跨 category 组合。
- **关键差异——CBAC 的 category 支持析取(disjunctive / OR)**:用户持有该 category 中**任一** marking 即可访问,用于 releasability(可发布性,如 "country A **OR** country B")。这是与标准 marking(只合取 AND)的本质区别。
- **层级(clearance)**:Project 有 "maximum classification"(= allowed marking limit),更高分类的资源不能创建/移入更低上限的 Project;用户按 clearance 层级访问——**密级 ≤ 自己等级的都能看**。

> **⚠ 对抗验证更正 4(措辞收窄)**:不宜断言"分类不能与 marking/organization 同挂一个属性"。CBAC 官方明说 "can be combined with other access requirements like discretionary roles and mandatory markings"(同一资源上可与普通 marking 并存,取 AND)。更准确的表述是:**分类作为独立的 mandatory control 维度配置;同一个 mandatory control property 承载单一控制类型**(这是 property 的配置约束,不是 CBAC 概念层禁令)。

### 2.5 行 / 列 / 单元格级——两条实现路径

Palantir 提供两条实现精细过滤的路径,新旧两代范式:

**路径 A｜Restricted View(RV,数据集层,老范式)**
- 叠在 backing dataset 之上的一个**过滤层**,用 granular policy 按**用户属性**决定哪些行可见。
- **硬约束:RV 不能当 transform 输入**(逐字确认 "cannot be used as an input for transforms")。根因:行级权限无法在批管道中一致保持,所以安全边界**必须是终点**——不允许把过滤后的结果再喂进下游计算(否则等于给了"洗权限"的口子)。要转成常规 dataset 供下游用,唯有 **materialize**(需较高权限,且物化后**不再带 RV policy**)。
- input 更新时后台 build 自动重建 RV。
- **行级 marking 变体**:表里加一个 **STRING ARRAY** 列存该行的 marking ID,granular policy 把"用户的 markings"与这一列比较。

**路径 B｜Object / Property Security Policy(本体层,新范式,官方主推)**
- **Object security policy** = **行级**:决定某个对象实例整体是否可见。
- **Property security policy** = **列级**:只作用于选定的属性(列),配置项与 object policy 完全相同,但**不能含主键、每个属性最多一条**。
- **单元格级 = 两者组合**——原文 "user must pass **both** the object security policy **and** the property security policy to view the property value"。
- **失败语义(极重要,决定返回形态)**:
  - 不过 object policy → **整行(整个对象实例)不可见**。
  - 过了 object、但不过 property → **该属性值返回 `null`**(不是报错,是静默置空)。
- **默认继承** backing datasource 的全部 mandatory control(markings / organizations / classifications),可在此基础上增删。
- **物化(materialize)时取"最严"权限**:合并所有源 marking + policy 新加的 marking(逐字确认 "most restrictive permissions")。

### 2.6 Granular Policy(RV 与 object/property policy 共用的判定内核)——实装规格

定义:"a set of rules and logical operators that compare user attributes, columns/properties, and values"。这是所有精细过滤的可编程内核,规格如下(全部经对抗验证逐字确认、数值零误差):

**支持的用户属性(精确名)**:
`User ID` / `Username` / `Group IDs` / `Group names` / `Authorized group IDs`(scoped session 用) / `Organization Marking IDs` / `Marking IDs` / IdP 配的 `Custom attributes`。

**8 种比较算子**:

| 算子 | 语义 | 约束 |
|---|---|---|
| `Equal` | 两边单值同类型相等 | |
| `Less Than` / `Greater Than` | 单值同类型大小比较 | **object security policy 不支持大小于类** |
| `Less-or-Equal` / `Greater-or-Equal` | 单值同类型 | **object security policy 不支持大小于类** |
| `Intersects` | 两集合有交集 | 至少一边是集合 |
| `Subset of` | 左 ⊆ 右 | 右边须是集合 |
| `Superset of` | 左 ⊇ 右 | 左边须是集合 |

**硬约束(照实现必守)**:
- **每策略最多 10 个比较**。
- **至少一项须与"用户属性"比较**(否则不是"按人过滤")。
- **引用 user / group / org 必须用 UUID,不能用名字**(原文 "Specifying names instead of IDs is not supported"——防改名后策略错乱)。
- **policy 列须非空**:policy 引用的列若为 `null`,该行不可访问。

**权重制(防策略过复杂导致性能塌方)**:

| 比较类型 | 权重 |
|---|---|
| 常量 vs 字段 | 1 |
| 集合 vs 字段 | 1000 |
| marking 条件 | 3000 |

- 单策略总权重上限 **< 10000**。
- property policy 与 object policy 的 granular 权重**合计**须 < 10000。

### 2.7 行级 marking = Mandatory Control Property(精确 schema)

把某个属性设为 "Mandatory Control" 基类型,即可把强制 marking 下沉到**行级**:

- base type = **Mandatory Control**;值类型 = **STRING ARRAY**,存 marking ID / organization ID。
- 配置步骤:
  1. 建 marking-backed RV + marking 列;
  2. Ontology Manager 里把属性映射到该 marking 列;
  3. 属性 sidebar 设 base type = Mandatory Control;
  4. 配 allowed values(allowed markings / organizations,或 CBAC 下的 max classification);
  5. **设 required**——强制不可空,原文 "mandatory control properties must be required";
  6. 多数据源对象(MDO)每个 datasource 各配一个。
- **访问语义**:markings + orgs 组合时 = **全部 marking 都持有(AND) 且 至少属于一个 org**;CBAC 下 = 层级访问(密级 ≤ clearance)。
- 一个 mandatory control property 可以为**同一 datasource 内的其它所有属性**提供行级保护。

### 2.8 Purpose-Based Access Control(PBAC,目的层)

在强制 + 自主之上,再叠一层"**为什么要访问**"的目的门:

- 访问权授予 **Purpose(目的)** 而非个人。用户申请加入某个 Purpose(由治理团队设定,范围恰好够达成目标——"no more, no less")。
- **双向记录 rationale**:数据 owner 批准"某数据集可用于某 Purpose"时须记录理由;用户获批加入 Purpose 时治理团队也须记录理由。强制双方持续评估必要性 / 相称性。
- 请求-审批-调用由 **Approvals 应用**统一管理(合规 / 治理 / 同行评审 workflow),可审计"某人当初为何获权"。

### 2.9 写回(Action)权限——独立于读的执行门

**跑一个 Action 需三件事同时满足**:
1. 能 **view** 被编辑的对象类型 / link 类型 / 其 datasource;
2. 通过 **submission criteria**(提交条件);
3. 满足对象类型的 **writeback 设置**。

**writeback 两模式**:

| 模式 | 编辑入口 | 所需权限 | 效果 |
|---|---|---|---|
| **(a) 仅限 Action 编辑**(新对象类型默认,推荐) | 只能经 Action | 对被编辑对象只需 **Read** | **可改自己看不全的记录**——"users can modify records they cannot independently view" |
| **(b) 放开** | Action + Forms + Object Explorer + API 均可编辑 | 须对 writeback dataset 有 **Edit** | 会带来更宽的数据可见性,官方明确 "discouraged" |

**Submission criteria(谁能提交的细粒度门)**:
- **Current-User 模板**:比对当前用户——`User ID` / group 成员 / multipass 字符串列属性(如 department)。
- **Parameter 模板**:比对 action 参数 / 对象属性 / linked 对象属性 / list。**不支持 attachment / object-set 参数**。
- **算子**:
  - 单值:`is` / `is not` / `matches`(正则) / `is less than` / `is greater than or equals`(注:官方所示为子集,非穷举,实现以编辑器实际可选项为准);
  - 多值:`includes` / `includes any` / `is included in` / `each is` / `each is not`;
  - 逻辑组合:`All` / `Any` / `None`,**可嵌套**;每根条件带一句**失败提示语(failure message)**。
- **Side effects**(webhook / 通知)另需权限;通知**收件人须对通知引用的对象数据有访问权**,无权则**跳过该收件人、Action 仍成功**(原文 "If notifications fail to send … edits may still succeed")。

### 2.10 Download / Export——第三根权限轴

download **独立于 view**,是与读、写并列的第三根权限轴:

- **Viewer / Editor / Owner 可 download;Discoverer 有 view 无 download**——"应能看不应能下"时授 Discoverer,或建自定义 Role 去掉 download workflow 保留更高权限。
- **Download category 支持 checkpoint**:下载前须确认政策 / 填理由,使下载成为一次 "intentional action"。
- **Cipher 加密**使下载物仍为密文,除非有解密权。
- `dataExport` 审计 category 记录每次下载(含 `downloadedSize` 字节数)。
- **官方声明有覆盖缺口**(逐字确认):"Not all download actions in Foundry are governed by roles"(例:SAML metadata 在 Control Panel 管)、"Not all download actions … are covered by a checkpoint"。此缺口真实存在,不可假定 download 被 100% 治理。

---

## 三、判定流程 / 配置形态

### 3.1 读权限判定的完整流程(一次 SELECT 的判定链)

一次读请求命中一份资源时,Palantir 依次过五道门(任一不过即失败,失败语义各异):

```
用户请求读资源 R（携带身份：user_id + groups + markings + orgs + clearance + purpose）
        │
   ①【发现门 / discovery】user 是否有资格看到 R 存在？
        │  否 → R 在搜索/目录中根本不出现（连"存在"都不暴露）
        ▼ 是
   ②【强制门 / Mandatory】user_markings ⊇ R 的全部标准 marking(AND)
        │  且 CBAC category 内至少命中一个(OR)、密级 ≤ clearance
        │  且 user 至少属于 R 要求的一个 organization
        │  否 → 整个资源拒绝（deny-overrides，与角色无关）
        ▼ 是
   ③【自主门 / Discretionary】user 在 R(或其祖先 Project/folder)上是否有 Viewer 及以上 Role？
        │  否 → 拒绝读
        ▼ 是
   ④【行级 / Object policy】逐行跑 granular policy（比对用户属性 vs 行的 marking 列/属性）
        │  某行不过 → 该行从结果集中消失（整行不可见）
        ▼ 过的行
   ⑤【列级 / Property policy】对受保护属性逐个跑 property policy
        │  某属性不过 → 该属性值返回 null（单元格级屏蔽，非报错）
        ▼
   返回结果（已按行过滤、按单元格置 null）
        │
   （若请求是下载/导出）⑥【下载门】须 Viewer+ 且非 Discoverer；命中 checkpoint 则要求填理由
```

关键点:
- ②③ 是**资源级**判定(过/拒整份资源);④⑤ 是**行/单元格级**判定(部分可见)。
- ② 与 ③ 是 **AND**:强制门决定"绝对下限",自主门决定"能否协作";任一不过都读不到。
- **失败语义分层**:强制/自主不过 → 整份拒绝;object policy 不过 → **整行消失**;property policy 不过 → **该格 = null**。这个"三档失败"是返回形态设计的关键。

### 3.2 写权限判定的独立流程(一次 Action 的判定链)

写路径**不复用**上面的行/列可见性判定,是一条并行独立的门:

```
用户提交 Action A（改对象 O 的若干字段）
        │
   ①【view 门】能否 view O 的对象类型/link 类型/其 datasource？
        │  否 → 拒绝（注意：这里只要求 view 对象类型，不要求通过 O 的行级可见性）
        ▼ 是
   ②【submission criteria】跑 All/Any/None 逻辑树，用 is/matches/includes... 等算子
        │  比对 caller 属性 + action 参数 + 目标对象属性
        │  否 → 拒绝，回显该根条件的 failure message
        ▼ 是
   ③【writeback 模式门】
        │  (a) 仅限 Action 编辑：只查 O 的 Read → 可改自己看不到的行
        │  (b) 放开：须对 writeback dataset 有 Edit
        ▼ 全过
   apply：事务式落库 + 记 lineage
        │
   （可选）side effects：webhook/通知；收件人无权引用对象则跳过该收件人，Action 仍成功
```

对比读流程的本质差异:**写流程第 ③ 步的 "(a) 仅限 Action 编辑" 模式只查 `Read`,完全不跑 ④行级/⑤列级过滤**——这正是"改自己看不到的记录"得以成立的机制点。

### 3.3 Marking 配置形态

- Marking 是中央资源,由治理团队在 Control Panel / 平台管理界面创建,归属某个 **Marking Category**。
- **Create Marking API** 字段:`name`(必) / `description`(否) / `categoryId`(必) / `initialMembers`(否) / `initialRoleAssignments`(否,至少 1 个 ADMINISTER);响应含 `id` / `categoryId` / `name` / `description` / `organization`(RID `ri.multipass..organization.<UUID>`) / `createdTime` / `createdBy`。
- **Organizations 是一种特殊 Marking**(逐字确认 "Organizations are a special category of Markings"),其 `categoryId` 为字面量 `"Organization"`,API 关键字为 `OrgMarkings`。
- 给资源**贴** marking 后 saved 即生效并向下游传播;**移除**须 `Remove marking` 权限(见更正 2)。

### 3.4 行 / 列过滤机制的硬细节(照实现必留)

**行级(marking-backed,最常用)——granular policy 示例**:
- 左操作数 = 用户的 `Marking IDs`(集合);
- 算子 = `Superset of`(用户的 marking 集合须 ⊇ 该行 marking 列)或 `Intersects`(有交集即可,视语义);
- 右操作数 = 该行的 marking 列(STRING ARRAY);
- 多列时各建一条 rule,用 `All`(AND)/`Any`(OR) 组合。

**行级(属性匹配,如按地区/部门)**:
- 左 = 用户 `Custom attributes` 中的 `region`;
- 算子 = `Equal`;
- 右 = 表的 `region` 列。

**列级(property policy)示例**:
- 前提:object policy 已存在(行已过);
- 选一个**非主键**属性(如 `unit_price`);
- 加 granular policy 比对某用户属性(如"是否属于财务 group");
- 不通过 → 该属性返回 `null`(而非整行消失、也非报错)。

**三条必守的机制约束(否则复刻不成立)**:
1. **安全边界必须是终点**:过滤逻辑所在的层不能再被当作下游计算的输入(RV 不可作 transform 输入)。否则任何人都能"过滤一次→物化→绕过过滤"。
2. **policy 列 NOT NULL**:marking 列/属性列若可空,`null` 行会造成判定歧义——Palantir 直接规定"policy 列 null 行不可访问",且 mandatory control property "must be required"。
3. **一切用 UUID**:policy 里引用 user/group/org 一律 UUID,禁用名字——防止改名后策略静默失效。

---

## 四、映射到DataSteward 栈(我们怎么复刻)

我们的栈:StarRocks(OLAP 只读数仓)/ PostgreSQL(OLTP 源)/ Flink CDC(增量同步)/ Neo4j(图/血缘)/ pgvector(语义检索)/ 只读 MCP 连接器 + JSONL 审计 / 无头 Claude(`claude -p`)/ Streamlit 治理台。核心复刻思路:**把"策略做成数据",把"强制判定放进只读 MCP 这个唯一读入口",把"写回"另开一条独立通道。**

### 4.1 策略即数据——`security/` 元表(落 PostgreSQL)

策略元数据要频繁读写、要事务性,放 **PostgreSQL**(不要放只读的 StarRocks 仓):

```
markings(marking_id UUID PK, name, category_id, kind ENUM['standard','cbac','org'], is_disjunctive BOOL)
    -- 复刻 Marking + Category + CBAC；is_disjunctive=true 表示该 category 内 OR（CBAC releasability）
user_markings(user_id, marking_id)                 -- 用户持有的 marking（对应 IdP 属性）
resource_markings(resource_type, resource_id, marking_id)  -- 表/列/对象贴的强制标签
roles(role_id, name, rank INT)                      -- 固定 4 行 Owner/Editor/Viewer/Discoverer
role_grants(subject_id, resource_id, role_id)       -- 沿资源树继承（物化路径或递归 CTE）
granular_policies(policy_id, target_type ENUM['object','property'], target_id, expr JSONB)
    -- expr 存 rules 数组 [{left:user_attr, op:ENUM(8种), right:{col|const}}] + 逻辑树 All/Any/None
purposes(purpose_id, name, rationale)
purpose_datasets(purpose_id, table, approver, rationale)   -- PBAC：数据可用于某目的（记 rationale）
purpose_users(purpose_id, user_id, approver, rationale)    -- PBAC：用户获准加入某目的（记 rationale）
```

`granular_policies` 的实现里**强制三条校验**(照 Palantir 硬约束):`expr` 中比较数 ≤ 10;至少一项比较左操作数是用户属性;按权重表(常量=1/集合=1000/marking=3000)累加 < 10000。

### 4.2 强制层在只读 MCP 连接器实装

只读 MCP(`src/dm/connector/mcp_server.py`)是无头 Claude 读数据的**唯一入口**,天然是"安全边界的终点"——调用方(Claude)拿不到 StarRocks 直连,只能经 MCP,**绕不过**,精确复刻了"RV 不可作 transform 输入"这一硬约束。

在 MCP 的 `run_sql` 等工具**返回结果前**,用 **caller 身份**(从 mcp-config 注入的 `DM_USER` / `DM_ROLE` + `purpose_id`,连同 `session_id`)做四道过滤:

```
run_sql(caller=DM_USER, role=DM_ROLE, purpose=purpose_id, sql=...):

  0)【目的门 PBAC】查 purpose_users：DM_USER 是否在 purpose_id？
     查 purpose_datasets：purpose_id 是否获批访问 sql 命中的每张表？
     否 → 拒绝 + 写 authorizationCheck(denied, reason=purpose)

  1)【强制门 Markings】对 sql 命中的每张表：
     resource_markings(该表的标准 marking) ⊆ user_markings(DM_USER)？   -- AND
     CBAC category 内 is_disjunctive 的至少命中一个？                    -- OR
     否 → 整表拒绝 + 写 authorizationCheck(denied, reason=marking)

  2)【自主门 Role】role_grants：DM_ROLE 在该表(或祖先)上 ≥ Viewer？
     否 → 拒绝读
     （Discoverer → 允许元数据、禁读内容/禁导出）

  3)【行级】对敏感表用 caller 身份重写 SQL、注入 WHERE：
     - marking-backed：  WHERE row_markings <@ :user_marking_array   -- PG 数组"被包含于"算子
       （StarRocks 侧对应 array_contains 全量匹配；见 4.3）
     - 属性匹配：        WHERE region = :user_region
     WHERE 由连接器注入，Claude 拿不到底表 → 绕不过（复刻"安全边界是终点"）

  4)【列级】按 property policy，把无权列在返回 JSON 里置 null（复刻"property 失败返回 null"）：
     - 关键：返回 schema 里加 _redacted 标记，区分 null="无权" vs null="数据缺失"
       （否则 Claude 无法分辨,可能误判为数据质量问题）
```

**判定顺序对齐 §3.1**:目的门 → 强制门 → 自主门 → 行级 → 列级。资源级(0/1/2)一票否决整表;行/列级(3/4)做部分可见。

### 4.3 行级 marking 列(StarRocks 敏感表)

在 StarRocks 的敏感表(如客户/成本/合同)加一个 `ARRAY<STRING>` 列存该行的 marking ID:
- 建模时置为 **NOT NULL**(复刻 Palantir mandatory control property "must be required" 语义);
- 值由 **Flink CDC 从 PostgreSQL 源带过来**(源表维护该行的 marking);
- MCP 行级过滤时:PG 侧策略语义是 `row_markings <@ user_marking_array`(用户 marking 集合须 ⊇ 该行);StarRocks 侧用 `array_contains` 对该行每个 marking 逐一校验 caller 是否持有。

这精确对应 Palantir 的 **Mandatory Control Property**(base type=Mandatory Control、STRING ARRAY、required)。

### 4.4 角色与 Markings 的DataSteward 实例

结合制造业角色,给出一套最小可用的 `security/` 初值:

| 角色(role) | 对应岗位 | 典型 Marking 资格 | 说明 |
|---|---|---|---|
| **采购** | 采购员 | `PII`(供应商联系人) | 可见供应商/采购单;财务列(采购价合同条款)按列级屏蔽 |
| **仓管** | 仓库管理员 | (无敏感 marking) | 可见库存/物料/出入库;客户 PII、成本价均屏蔽 |
| **生产** | 生产计划 | (无敏感 marking) | 可见 BOM/工单/产能;不见价格与客户联系方式 |
| **管理层** | 厂长/经理 | `PII` + `FIN` | 两 marking 齐备 → 可见客户联系方式 + 财务字段(AND 语义) |
| **管理员** | 平台管理员 | 按需 | 管 `security/` 元表 CRUD;注意:管权限 ≠ 自动获数据资格(强制层否决式仍适用) |

Markings(强制层)建议起步集:
- `PII`:客户/供应商联系人、身份证等个人信息列;
- `FIN`:采购价、销售价、成本、合同金额等财务列。

两者**合取**:管理层同时持有 `PII` + `FIN` 才能看"某客户的成交价";只持 `PII` 的采购员看得到客户联系人但看不到财务列(列级 null)。

### 4.5 写回权限独立校验(另开通道,不走只读 MCP)

当前栈全只读、无写回,这是最大缺口。要复刻"改看不到的记录",另开一个"**Action 执行**"通道(**不走**只读 MCP):

```
action_types(action_id, target_table, submission_criteria JSONB, writeback_mode ENUM['action_only','open'])

执行校验（对齐 §3.2）:
  ① view 门：caller 能 view target_table 的对象类型？（不查行级可见性）
  ② submission criteria：用 All/Any/None + is/matches/includes 等算子
     对 caller 属性 + action 参数判定；失败回显该条 failure_message
  ③ writeback_mode:
       'action_only' → 只查 target 的 Read（复刻"改自己 SELECT 不到的行"）
       'open'        → 须对 writeback 目标有 Edit
  全过 → 执行写回
```

**写回落点与闭环**:StarRocks 只读,写回须**回写 PostgreSQL 源**(OLTP 事务强),再由 **Flink CDC 流回 StarRocks** 形成闭环。每次执行写 `requestCreate` / `requestExecute` 审计。最小可行 Action = `shipOrder`:submission criteria 用 `is greater than or equals` 实现"库存 ≥ 需求",writeback 落 PG,side effect = 钉钉推送(≈ Notification)。

### 4.6 沿血缘并集传播(接 Neo4j 补,当前短板)

当前仓库是静态、无 transform DAG,marking 传播缺失。上生产后用 Neo4j 存血缘图 `(:Dataset)-[:DERIVES]->(:Dataset)`:每次 Flink CDC / 建模产出新表时,跑一次图遍历,把**上游全部 marking 取并集**写进新表的 `resource_markings`——复刻"marking 沿血缘并集继承、工程师洗不掉"。前置条件:dbt/Flink 作业须注册血缘边。触发点(建模作业结束钩子 vs 定时 reconcile)见 Open questions。

### 4.7 审计与治理台

- **审计**(JSONL append-only,已对范式):补 `category` 化(`dataLoad` / `dataExport` / `authorizationCheck` / `managementPermissions` / `requestExecute`),每条必带 who + what + when + purpose + `trace_id`(= `session_id`);**把上面各道门的 denied 也写进 `authorizationCheck`**(合规首查项)。归档 JSONL 设为进程只追加、连管理员不可改。
- **Streamlit 治理台**(`src/dm/app/app.py`)新增:
  1. **Markings / Roles / Purposes 管理页**:CRUD 上述 `security/` 元表;
  2. **"权限判定回放"页**:输入 `user_id` + `table`,逐门展示判定结果(过/拒 + 原因),精确复刻 Palantir 的 "Test security policies" modal——这是把治理台当**调试工具**的核心用法;
  3. **审计浏览**:按 `trace_id` / `category` / `denied` 过滤,接现有"按 session_id 回放任务链"。

### 4.8 落地优先级(按 ROI)

1. **MCP 里补 Markings 强制门 + 列级 null 屏蔽**(客户 PII、财务列)——收益最大、改动集中在 `mcp_server.py`;
2. `session_id` 升级为 `purpose` 句柄 + 事前审批白名单(PBAC);
3. 审计 category 化 + denied 落盘 + 治理台判定回放;
4. Neo4j 血缘并集传播(等有 transform DAG);
5. 写回 Action 通道 + submission criteria(补最大缺口)。

---

## 五、Open questions

1. **granular policy 权重上限的口径**:官方在不同页给了两个数——manage-granular-policies 页说单策略 < 10000(marking 条件=3000、集合=1000、常量=1),object-security-policies 页又提"object + property 合计 comparison limit of 10,000"。是同一上限还是分别 10000,需实测;对我们只是校验阈值,**先取保守"合计 < 10000"**。
2. **"每策略最多 10 个比较" vs "权重 < 10000" 哪个先触顶**、是否同时生效,官方未并列说明。实现时两条都校验。
3. **CBAC 分类层级枚举**:官方不给固定枚举(UNCLASSIFIED/CONFIDENTIAL/SECRET… 因机构而异、需 Palantir 介入)。制造业客户大概率用不到军规 CBAC,**标准 marking(PII/FIN)已足够**;若需多级密级,得自定义层级枚举——属决策项。
4. **行级安全按"表"还是按"本体对象"过滤**:Palantir 官方主推本体层(object security policy),但我们本体层做多厚取决于 Neo4j 的角色——若 Neo4j 只做图查询、未建完整对象层,则**先在 MCP 按表注入 WHERE 更现实**。
5. **`null` 语义歧义**:"property 失败返回 null" 与 "数据本就缺失" 在 JSON 返回里无法区分,Claude 智能体可能误判。**需在返回 schema 里加 `_redacted` 标记**区分"无权"vs"缺失"——属实现决策(§4.2 第 4 步)。
6. **scoped session / Authorized group IDs(用户会话内自我降权)是否需要**:对无头 Claude agent,或许用"每 purpose 一套受限 marking 集"来近似即可,需决策。
7. **marking 沿血缘并集传播的触发点**:Palantir 在每次 build 自动做;我们无统一 build orchestrator(Flink CDC + 建模脚本混合),何时/由谁触发图遍历更新下游 marking——可考虑**建模作业结束钩子**或**定时 reconcile**,需定。
8. **写回"改自己看不到的记录"在只读仓 + CDC 架构下落哪**:StarRocks 只读,写回须回写 PG 源再由 CDC 流回,这条**回写路径的权限与审计链需专门设计**(事务边界、失败回滚、双写一致性)。

---

## 六、来源

**权限主线(f_permissions 调研)**:
- https://www.palantir.com/docs/foundry/security/overview
- https://www.palantir.com/docs/foundry/security/markings
- https://www.palantir.com/docs/foundry/security/projects-and-roles
- https://www.palantir.com/docs/foundry/platform-security-management/manage-roles
- https://www.palantir.com/docs/foundry/platform-security-management/manage-markings
- https://www.palantir.com/docs/foundry/platform-security-management/manage-granular-policies
- https://www.palantir.com/docs/foundry/security/classification-based-access-controls
- https://www.palantir.com/docs/foundry/security/restricted-views
- https://www.palantir.com/docs/foundry/object-permissioning/object-security-policies
- https://www.palantir.com/docs/foundry/object-permissioning/managing-object-security
- https://www.palantir.com/docs/foundry/object-permissioning/ontology-permissions
- https://www.palantir.com/docs/foundry/object-link-types/mandatory-control-properties
- https://www.palantir.com/docs/foundry/security/property-security-markings
- https://www.palantir.com/docs/foundry/action-types/permissions
- https://www.palantir.com/docs/foundry/action-types/submission-criteria
- https://www.palantir.com/docs/foundry/object-edits/permission-checks
- https://www.palantir.com/docs/foundry/security/download-controls
- https://www.palantir.com/docs/foundry/security/security-glossary
- https://www.palantir.com/docs/foundry/security/audit-log-categories
- https://blog.palantir.com/purpose-based-access-controls-at-palantir-f419faa400b3
- https://www.palantir.com/docs/foundry/approvals/overview

**对抗验证补充来源(_verifications,permissions 维度)**:
- https://www.palantir.com/docs/foundry/security/protecting-sensitive-data
- https://www.palantir.com/docs/foundry/object-permissioning/ontology-permissions-legacy
- https://www.palantir.com/docs/foundry/platform-security-management/manage-orgs-and-spaces
- https://www.palantir.com/docs/foundry/building-pipelines/remove-inherited-markings
- https://www.palantir.com/docs/foundry/api/admin-v2-resources/markings/create-marking
- https://www.palantir.com/docs/foundry/api/v2/admin-v2-resources/organizations/organization-basics
