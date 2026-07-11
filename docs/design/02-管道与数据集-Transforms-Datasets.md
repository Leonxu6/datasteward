# 02 · 管道与数据集（Transforms & Datasets）

> **一句话定位**：把"源系统的原始数据"变成"可信、可复用、可增量刷新的业务表"的那一层——Palantir 用一套**声明式、版本化、血缘自动**的构建系统实现；对应我们平台的 **StarRocks 数仓（raw/refined 分层）+ Flink CDC 增量同步 + 转换注册表（血缘）** 这一层，即介于「连接器落地」与「本体建模」之间的加工环节。

---

## 一、解决什么问题（第一性原理）

数据从源系统（ERP、MES、OLTP 库）到能被业务和 AI 消费，中间必然要经历"抽取 → 清洗 → 转化"（ELT）。这层最容易失控的四个问题：

1. **依赖关系靠人脑记**：A 表由 B、C 算出，B 又依赖 D……手写调度脚本时，改一张表要人肉排查"谁受影响、按什么顺序重跑"。规模一大，血缘就断了。
2. **全量重算太贵**：每次刷新都把千万行整表重算，既慢又浪费；但"只算新增的"又容易算错（漏行、重复、聚合口径错）。
3. **脏数据静默流下游**：源端 schema 一漂移、字段一变类型，坏数据一路灌进下游，等到 dashboard 才发现，已经污染了一大片。
4. **改逻辑没法安全试**：想改一段转换逻辑，直接改就影响线上；没有"分支 / 版本 / 回滚"就不敢动。

Palantir 的答案是把这层当成**一个构建系统（build system）**来治理，而不是一堆脚本：
- **分层**（raw → clean → canonical）把"原样落地""显式清洗""业务规范"三种关注点物理隔开；
- **声明式转换**（`@transform` 登记输入/输出）让框架**自动推导 DAG、自动画血缘、只重算受影响下游**；
- **不可变事务 + 增量语义**让"只算新增"变成框架保证的、可回退的操作；
- **数据期望（Data Expectations）**把质量校验前移成**构建期门禁**，脏数据在落库前就被拦截。

一句话：**把"写数据管道"从命令式脚本，升级成"声明依赖 + 框架负责调度/增量/血缘/门禁"的工程化系统。**

---

## 二、Palantir 怎么做（机制）

### 2.1 `@transform` 装饰器：声明输入/输出 → 自动血缘

转换代码写在 Code Repositories 里，用装饰器声明"这个函数吃哪些 Dataset、产出哪个 Dataset"。三个核心装饰器：

| 装饰器 | 形态 | 说明 |
|---|---|---|
| `@transform` | 函数收到 `TransformInput` / `TransformOutput` 对象，自己调 `.dataframe()` 读、`.write_dataframe()` 写 | 最通用；可注入 `ctx=TransformContext` 拿 `ctx.spark_session` / `ctx.is_incremental` / 文件系统句柄；可 `out.abort()` 中止 |
| `@transform_df` | 函数 `return` 一个 Spark DataFrame 即写出，`Output` 作第一个位置参数、输入作关键字参数 | 最常用，写法最简 |
| `@transform_pandas` / `@transform_polars` | 同形态，DataFrame 换成 pandas / polars | 小数据/单机逻辑 |

**关键机制**：装饰器把"函数参数 = 输入 Dataset、返回值 / Output = 输出 Dataset"这层映射**登记给构建框架**。框架据此**自动拼出 DAG、拓扑排序、决定并行与增量范围**——工程师不需要手画依赖图，也不需要写调度脚本。血缘图不是额外维护的产物，而是这些声明的**副产品**：因为 sync 产物和 transform 的输入/输出都是同一个 Dataset 抽象，框架每次 build 天然知道上下游，累积即端到端血缘。

声明类：
- `Input(path, branch=?, alias=?, description=?)`、`Output(path, sever_permissions=?)`；
- `Markings(marking_ids, on_branches)` / `OrgMarkings(...)`：让某 marking 停止向下游传播（权限相关）；
- 参数类 `StringParam` / `IntegerParam` / `FloatParam` / `BooleanParam(default, description)`。

### 2.2 raw / clean / canonical 分层（硬约定的三段式项目）

分层不是建议，而是**固定的项目结构约定**。层级：`raw → clean → canonical → ontology`，由三类项目承接：

| 项目 | 输入 | 产出 | 关键约定 |
|---|---|---|---|
| **Datasource Project** | Data Connection 的 sync | **raw**（尽量原样落地）→ **clean** | 官方明确：**即便 schema 推断已选对类型，也要在 raw→clean 显式 `cast` 每列类型**，套统一 schema |
| **Transform Project** | 一或多个 Datasource 的 clean 数据集 | **canonical**（规范、可复用） | 跨项目 `import` clean 数据集，转成业务规范表 |
| **Ontology Project** | Transform 的 canonical | 对象表 → 映射到本体对象 | 代表离散业务对象的规范表 |

每类项目内固定目录约定：
- `/clean`（清洗后数据集）、`/logic`（转换逻辑代码）、`/output`（最终可消费数据集）、
- `/analysis`（测试/文档用、展示数据形状）、`/scratchpad`（构建临时资源）、
- `/documentation`（Data Lineage 血缘图 + 额外文档）、`/datasets`（数据集引用/配置）。

命名约定：数据集 / 列 / 仓库 / 文件都用**两三词、能让读者立刻明白用途**的名字，常见前缀 `stg_` / `int_` / `dim_` / `fct_`。

### 2.3 数据集与事务：版本化地基

Dataset **不是"可原地 UPDATE 的行表"**，而是：**底层文件集合（常 Parquet）+ schema（挂在文件集合上的一层元数据）+ 事务历史 + 可分支**。每次写入 = **一个原子不可变事务**。这是增量、回滚、分支能成立的地基。

**四种事务类型**：

| 事务类型 | 语义 | 用途 |
|---|---|---|
| `SNAPSHOT` | 整体替换当前视图的**全部**文件 | 批管线基础；**打断下游增量** |
| `APPEND` | 只加新文件、**不能改**已有文件 | 增量管线基础 |
| `UPDATE` | 加新文件**且可覆盖**已有文件内容 | 部分分区更新 |
| `DELETE` | 删文件 | 多与保留（retention）策略相关 |

- 事务状态：`OPEN` / `COMMITTED` / `ABORTED`。
- **"当前态"（view）如何算出来**：从该时点前**最近的一个 SNAPSHOT** 事务开始（若无 SNAPSHOT 则取最早事务），对 `SNAPSHOT`/`APPEND` 把事务文件**全部加入**集合，对 `UPDATE` 加入并**替换同名文件**——这就是当前视图的解析规则。

### 2.4 增量 vs 快照构建

增量的本质是**"只处理上次成功 build 以来变化的数据"**，由"不可变事务历史"支撑。开关是叠在 `@transform` 之上的 `@incremental()` 装饰器：
- `input.dataframe('added')` → 只读上次成功 build 以来新增/更新的行；
- `output.write_dataframe(df, mode='modify')` → 只追加 / 更新，而非全表重算。

**Foundry 用四项检查决定"这次跑增量还是回退全量快照"**：
1. **输入变更分析**：输入事务是否只有 append-only 变更（`APPEND`/`UPDATE` 可增量），有 `SNAPSHOT` 则打断；
2. **输出血缘检查**：输出上次是否由**同一个 transform** 构建；
3. **输入一致性**：非快照输入的起始事务与上次运行匹配；
4. **`semantic_version` 未变**。

四项全过才跑增量，否则自动回退全量快照重建。（增量的完整参数语义见第三节。）

### 2.5 Build / Schedule / 触发器

- **Build = 一次管线执行**：读输入 Dataset 某版本 → 跑转换 → 产出输出 Dataset 的**一个新事务**。框架从 `@transform` 声明自动推导依赖图、按拓扑序调度、能并行则并行、**只重算受影响下游**。
- **Schedule 触发类型**：
  - **时间触发**：cron 表达式（UI 也可无代码配简单时间触发）；
  - **事件触发（4 种）**：`New logic`（某数据集的计算逻辑被更新）、`Data updated`（有事务提交更新了某数据集）、`Job succeeded`（某数据集上的 job 完成）、`Schedule ran successfully`（某调度构建成功完成）；
  - **复合触发**：`AND trigger`（合取）/ `OR trigger`（析取）组合多个组件触发。
- 官方建议：把 **Data Connection sync 与其余 build 分开调度**，以便只对 sync 做 force-build。

### 2.6 分支与版本化数据集

数据集可以**像代码一样开分支**：
- 默认主分支（master）**受保护**；
- 改转换逻辑时在 feature 分支跑 build，**不影响主线**；验证 OK 再合并回主分支。

配合不可变事务历史，这让"改逻辑→安全试→回滚"成为一等能力，而不是靠备份表硬扛。

### 2.7 事务模型与数据期望（构建门禁）

**数据期望（Data Expectations）** 把质量校验变成**构建时门禁**，而非事后 dashboard：
- `Check` 类包一个 expectation 注册到 Data Health，`on_error` 决定失败行为：
  - `FAIL`（默认）：**中止 job、回滚输出事务**——脏数据不落下游；
  - `WARN`：记违规但放行，交 Data Health 处理。
- expectations 模块常导入为 `E`，可用 `E.all()` 把多个列期望合起来。
- 上游 schema 一漂移，schema 期望在**落库前**就发现"输入与约定不符"，按 `FAIL`/`WARN` 触发——把数据质量从"事后发现"变成"构建时拦截"。

这与事务模型咬合：因为写入是原子事务，`FAIL` 时可以干净地回滚整个输出事务，不留半截脏数据。同理 `@transform` 里遇到空输入可调 `out.abort()` 中止 job、回滚所有输出事务。

---

## 三、字段 / 配置 / 代码形态

> 本节保留 transform 形态、增量语义、版本/分支的**硬细节**，供照抄。

### 3.1 `@incremental` 完整签名（照抄可用）

```python
@incremental(
    require_incremental=False,   # bool: True=不能增量就直接失败(除非从未跑过, 即所有输出无已提交事务)
    semantic_version=1,          # int: 逻辑改到使旧输出失效时手动+1 → 强制下次全量重算(快照重建)
    snapshot_inputs=None,        # list[str]: 这些输入的 SNAPSHOT 不打断增量; 支持 update/delete, 每次按全量读
    allow_retention=False,       # bool: True=foundry-retention 造成的删除不打断增量
    strict_append=False,         # bool: True 且跑增量时, 底层 Foundry 事务类型强制为 APPEND(只加不覆盖删)
    v2_semantics=False,          # bool: 启用 v2 增量语义, 官方建议都设 True(行为应与 v1 无差)
)
```

参数逐个语义：
- **`require_incremental`**：`True` 时除非 transform 从未跑过，否则拒绝非增量运行——跑不了增量就失败，而不是回退全量。
- **`semantic_version`**：转换逻辑的"语义版本"；逻辑改到会让旧输出失效时手动 +1，强制下次全量重算。
- **`snapshot_inputs`**：列出"即使来了 SNAPSHOT 事务也不使当前输出失效"的输入（典型是查找表 / 维表）。只有**除这些之外**的输入都只有 added / 无新数据时，transform 才跑增量；`snapshot_inputs` 里的输入支持 update/delete 修改，且每次按**全量**读。
- **`allow_retention`**：`True` 时 retention 删除不打断增量。
- **`strict_append`**：`True` 且跑增量时，底层事务强制为 `APPEND`（只加新分区、不覆盖删除）。
- **`v2_semantics`**：启用 v2 语义，官方建议都设 `True`。

### 3.2 读 / 写模式

**读** `input.dataframe(mode=...)`：
- `'added'`：增量跑 = 只返回本次新增/更新的行；非增量/快照跑 = 返回整表（全部视为"新"）。
- `'current'`：两种跑法都返回本次传入的**全量**数据。
- `'previous'`：增量跑 = 返回上一次 build 处理的输入/输出；**首次或大改后为空 DataFrame**——因此对 `output.dataframe('previous', schema)` **必须传 `schema`** 以正确构造空 DF。

**写** `output.write_dataframe(df, mode=...)` / `output.set_mode(...)`：
- `'modify'`：增量默认，追加或更新已有输出；
- `'replace'`：全量覆盖已有输出。

**运行时判定**：用 `ctx.is_incremental`（布尔）分支写"增量走 `added`、否则全量"的兼容逻辑。

### 3.3 基础转换代码形态

```python
# ---- @transform_df: return DataFrame 即写出 ----
from transforms.api import transform_df, Input, Output
@transform_df(
    Output("/manufacturing/clean/sales_orders"),
    raw_orders=Input("/manufacturing/raw/sales_orders"),
    materials=Input("/manufacturing/clean/materials"),
)
def compute(raw_orders, materials):
    return raw_orders.filter(raw_orders.status == "OPEN").join(materials, "material_id")


# ---- @transform: 拿 TransformInput/Output 对象, 可 abort(空输入不写) ----
from transforms.api import transform, Input, Output
@transform(
    out=Output("/Palantir/output_location/datasets/not_process_empty_files"),
    source_df=Input("/Palantir/input_location/sometimes_empty"),
)
def compute(source_df, out):
    source_df = source_df.dataframe()
    if len(source_df.head(1)) == 0:
        out.abort()                    # 空输入 → 中止 job, 回滚所有输出事务
    else:
        out.write_dataframe(source_df)
```

### 3.4 增量转换代码形态（几个官方范式）

```python
# ---- 最常见: 只处理新增行, 追加写 (added + modify) ----
from pyspark.sql import functions as F
from transforms.api import transform, incremental, Input, Output
@incremental()
@transform(
    incremental_data=Output("..."),
    sales_data=Input("..."),
)
def compute(sales_data, incremental_data):
    df = sales_data.dataframe(mode="added")
    df = df.withColumn("Time_stamp", F.current_timestamp())
    incremental_data.write_dataframe(df, mode="modify")


# ---- 快照维表 join 增量事实表 (snapshot_inputs) ----
@incremental(snapshot_inputs=["country_codes"])
@transform(
    phone_numbers=Input("/examples/phone_numbers"),   # 只读新增(added)
    country_codes=Input("/examples/country_codes"),    # 每次全量(current)
    output=Output("/examples/phone_numbers_to_country"),
)
def map_phone_number_to_country(phone_numbers, country_codes, output):
    phone_numbers = phone_numbers.dataframe()   # added
    country_codes = country_codes.dataframe()   # current(全量)
    ...


# ---- 增量聚合: 读 previous 输出 + union 增量 再聚合 ----
@incremental(semantic_version=1)
@transform(
    input_data=Input(""),
    daily_aggregate=Output(""),
)
def compute(ctx, input_data, daily_aggregate):
    input_df = input_data.dataframe()
    latest = input_df.groupBy(F.col("group_by_field")).agg(
        F.count_distinct(F.col("unique_thing")).alias("sum_of_unique"))
    if ctx.is_incremental:
        prev = daily_aggregate.dataframe(mode='previous', schema=latest.schema)
        merged = prev.unionByName(latest).groupBy("group_by_field").agg(
            F.sum("sum_of_unique").alias("sum_of_unique"))
        daily_aggregate.set_mode('replace')
        daily_aggregate.write_dataframe(merged)
    else:
        daily_aggregate.write_dataframe(latest)
```

### 3.5 数据期望（构建门禁）代码形态

```python
from transforms.api import transform_df, Input, Output, Check
from transforms.expectations import expectations as E
@transform_df(
    Output("...", checks=[
        Check(E.col("age").non_null() & E.col("age").gt(0) & E.col("age").lt(200),
              "age_valid", on_error="FAIL"),   # FAIL=中止回滚 | WARN=放行告警
    ]),
    src=Input("..."),
)
def compute(src):
    return src
```

### 3.6 事务 / 分层 / 调度 速查

```text
# ==== 事务类型 (Dataset 版本化原子单位) ====
# SNAPSHOT : 整体替换当前视图全部文件           → 批管线; 打断下游增量
# APPEND   : 只加新文件, 不改已有文件            → 增量管线基础
# UPDATE   : 加新文件且可覆盖已有文件内容        → 部分分区更新
# DELETE   : 删文件                             → 保留期清理
# 状态: OPEN / COMMITTED / ABORTED
# view 解析: 从最近 SNAPSHOT(无则最早事务)起, SNAPSHOT/APPEND 加全部文件, UPDATE 加并替换同名

# ==== 分层目录约定 (每类项目内) ====
# /clean /logic /output /analysis /scratchpad /documentation /datasets
# 层级: raw(Datasource Proj) → clean(显式 cast) → canonical(Transform Proj) → ontology(Ontology Proj)

# ==== Schedule 触发类型 ====
# 时间: cron
# 事件: New logic | Data updated | Job succeeded | Schedule ran successfully
# 复合: AND trigger(合取) / OR trigger(析取)
```

---

## 四、映射到DataSteward 栈（我们怎么复刻）

我们的栈：**StarRocks（OLAP 数仓）/ PostgreSQL（OLTP 源）/ Flink CDC（增量同步）/ Neo4j（图/血缘）/ pgvector（语义检索）/ 只读 MCP + JSONL 审计 / 无头 Claude / Streamlit 治理台**。这三件套（转换 / 分层 / 增量）可高保真复刻，核心思路是**把命令式 `dm-load` 建表升级成"声明式 DAG + 分层 + 增量物化 + 血缘"**。

### 4.1 转换层 = dbt on StarRocks（替代命令式 `dm-load`）

把 `dm-load` 的 19 表命令式建表迁到 dbt models：
- dbt 的 `ref('upstream')` **精确对应** `@transform` 的 `Input()`——都是"声明依赖，框架自动拼 DAG、拓扑排序、只重算受影响下游"；
- 一个 dbt model `.sql` = 一个 `@transform_df`（return 一张表）；
- dbt 的 `sources.yml` 声明外部源 = Foundry 的 Datasource sync 边界。
- StarRocks 有官方 `dbt-starrocks` adapter。

收益：立刻拿到"自动依赖图 + 增量物化 + 自带血缘"，即 Foundry 构建系统的开源精简版。

### 4.2 数据集分层 = dbt 目录 + StarRocks 库/schema 分层（raw + refined 两层）

按 Foundry 三段式落地目录：
- `models/staging`（= raw→clean，一源一 `stg_` 模型，**显式 `CAST` 每列**，对应 Datasource Project）→
- `models/intermediate` 或 `marts`（= clean→canonical，可复用业务表，对应 Transform Project）→
- `models/ontology`（= canonical→对象表，喂 Neo4j 图与 MCP，对应 Ontology Project）。

命名照 Foundry 约定：`stg_` / `int_` / `dim_` / `fct_` 前缀、两三词。**raw 层用 StarRocks 明细表原样落 CDC，clean 层显式 cast**——正好补上现有栈"源端漂移无落库前拦截"的缺口。

### 4.3 增量构建 = dbt incremental materialization + Flink CDC 高水位

`@incremental` 的语义在 dbt 里的对应：
- `{{ config(materialized='incremental', unique_key='...') }}` + `is_incremental()` 宏（= `ctx.is_incremental`）
- `WHERE updated_at > (SELECT max(updated_at) FROM {{ this }})`（= `input.dataframe('added')` 的"只读新增"）。
- dbt 的 `append` / `merge` / `insert_overwrite` incremental_strategy 分别对应 Foundry 事务 `APPEND` / `UPDATE(merge)` / `SNAPSHOT-of-partition`。
- **Flink CDC 复制槽的 WAL LSN = Foundry 的高水位游标**：Flink 负责"源→raw 增量 sync"，dbt 负责"raw→clean→canonical 增量 transform"。
- `snapshot_inputs`（维表全量、事实表增量）在 dbt 里就是"维表 model 全量物化、事实表 model incremental"的自然组合。

### 4.4 转换注册表 = 登记血缘（pipeline/ 目录）

在 `pipeline/` 建一份**转换注册表**登记血缘：
- dbt 自动生成 `manifest.json`（含 model 级血缘）+ dbt docs 血缘图，直接对应 Foundry Data Lineage 的"从转换声明自动长出";
- 进一步接 OpenLineage（dbt / Flink 都有 integration）发血缘事件给 Marquez，把端到端血缘（PostgreSQL 源 → raw → clean → canonical → Neo4j 对象）画进 **Streamlit 治理台**——把现有"按 `session_id` 回放任务链"升级成"按数据血缘调试"，呼应本仓约定"管理平台是调试工具"（CONTRIBUTING.md）。

### 4.5 事务 / 版本化 = StarRocks 明细分区 +（可选）Iceberg

StarRocks 本身无 Foundry 那样的 Dataset 事务分支。最小补法：
- 给 raw / canonical 关键表按日期分区（近似 SNAPSHOT-per-partition + `insert_overwrite` 重跑单分区）；
- 需要真"时间旅行 / 回滚 / 数据分支"时，给落库表上 **Apache Iceberg**（StarRocks 支持 Iceberg catalog），对应 Foundry 的事务历史 + branch。

### 4.6 构建门禁 = dbt tests / dbt-expectations（失败推钉钉）

把现有 `health.py` 的 `cdc_reconcile`（源汇行数对账雏形）升级成 Foundry 式 abort 级期望：
- dbt schema tests（`not_null` / `unique` / `accepted_values` / `relationships`）+ dbt-expectations 包（值域、行数区间）= `Check(..., on_error='FAIL')`；
- freshness = `dbt source freshness`（= Foundry Freshness 检查）；
- `on_error=FAIL` 对应 dbt test 失败即阻断下游 run；失败复用现有 `dm-dingtalk push` 告警。

### 4.7 调度 = Dagster 资产化（时间 + 事件）

- `dbt run` 的时间触发用 cron；
- Foundry 的"Data updated 事件触发"用 Dagster sensor 监听 Flink CDC 落库（新分区/新事务）后触发下游 dbt 资产重算，对应 Foundry 的 event trigger + AND/OR 复合触发；
- Dagster 的 asset lineage 也顺带给一张血缘图。

### 4.8 MCP 只读 + 审计不变

转换层产出的 canonical / ontology 表仍由现有只读 MCP 连接器暴露给无头 Claude，JSONL 审计不变；新增的是 build / 血缘 / 期望这套"**数据侧**"留痕，与现有"**智能体侧**"留痕互补。

### 对照速查

| Palantir Foundry | DataSteward 栈复刻 |
|---|---|
| `@transform` / `@transform_df` + `Input()`/`Output()` | dbt model `.sql` + `ref()` / `sources.yml` |
| 自动 DAG / 拓扑排序 / 只重算下游 | dbt DAG（`ref` 推导）；事件级用 Dagster sensor + asset selection |
| raw → clean（显式 cast）→ canonical → ontology | `models/staging`(CAST) → `intermediate`/`marts` → `models/ontology` |
| Dataset = 文件集 + 事务历史 + 分支 | StarRocks 明细表 + 日期分区；真分支/时间旅行上 Iceberg |
| 事务 SNAPSHOT/APPEND/UPDATE | dbt `insert_overwrite` / `append` / `merge` strategy |
| `@incremental` + `added`/`modify` + 高水位游标 | `materialized='incremental'` + `is_incremental()` + `updated_at` 高水位；源→raw 用 Flink CDC WAL LSN |
| Data Expectations（`Check`, `on_error=FAIL/WARN`）| dbt tests + dbt-expectations（失败推钉钉）|
| Data Lineage 血缘图 | dbt `manifest.json` + OpenLineage/Marquez → Streamlit 治理台 |
| Schedule（cron + 4 事件 + AND/OR）| cron（dbt run）+ Dagster sensor（事件/复合触发）|

---

## 五、Open questions

1. **v1 vs v2 增量语义的实际差异**：官方称"v2 只处理新/变数据且只写对应输出分区、行为应与 v1 无差"，但 v1 处理全部数据——这影响我们选 dbt incremental_strategy（append vs merge vs insert_overwrite）。需实测确认 v2 的分区级写入语义，及 dbt 侧哪种 strategy 最贴近。
2. **`'previous'` 读模式的确切切换条件**：文档说"逻辑或数据大改需重算时也为空"，但没给"大改"的精确判定（是否只看 `semantic_version` + 输入 SNAPSHOT）。dbt 用 `is_incremental()` + `this` 表是否存在来近似，边界行为需实测对齐。
3. **`snapshot_inputs` 与 `require_incremental` 同时设时的交互**：若维表来了 SNAPSHOT 但事实表只有 APPEND，`require_incremental=True` 时是否仍算"可增量"？官方措辞推断可增量，但需实测确认边界。
4. **事务粒度回滚 / 数据分支在开源栈的最简实现**：Foundry 的 Dataset branch + 回滚到任意历史事务是杀手锏；StarRocks 分区覆盖只是近似，Iceberg 才有真时间旅行/分支。是否值得为 PoC 引入 Iceberg（增运维），还是分区级近似够用——按数据量与"实验分支"实际需求决策。
5. **`strict_append=True` 与 StarRocks 主键表的冲突**：Foundry `strict_append` 强制 APPEND（不覆盖），但 canonical 表常需 upsert（主键更新）。哪些表走纯 append（事件流/日志）、哪些走 merge（维度/状态），需按表分类，不能一刀切。
6. **`Output(checks=...)` 与 `E` 模块的完整签名**：官方部分页面 JS 渲染，静态抓不全——`E` 模块完整期望函数全表（除 non_null/gt/lt/in_set/primary_key/schema/count/all/any 外还有哪些）、`Check` 确切关键字参数名，需登录 docs 或跑真实 repo 确认，再定 dbt-expectations 的映射清单。
7. **"事件驱动只重算受影响子图"在 dbt 上的完整度**：Foundry 上游一个新事务自动只重算受影响下游；纯 `dbt run` 是全图跑，需 `state:modified` + `defer` 或 Dagster 事件驱动才逼近。Dagster sensor + dbt asset selection 能否做到 model 级粒度，需实测。

---

## 六、来源

**转换 API / 增量：**
- https://www.palantir.com/docs/foundry/transforms-python/transforms-python-api
- https://www.palantir.com/docs/foundry/api-reference/transforms-python-library/api-incremental
- https://www.palantir.com/docs/foundry/transforms-python/incremental-overview
- https://www.palantir.com/docs/foundry/transforms-python/incremental-usage
- https://www.palantir.com/docs/foundry/transforms-python/incremental-reference
- https://www.palantir.com/docs/foundry/code-examples/incremental-transforms-transforms
- https://www.palantir.com/docs/foundry/code-examples/common-operations-transforms

**数据集 / 事务 / 分支：**
- https://www.palantir.com/docs/foundry/data-integration/datasets
- https://www.palantir.com/docs/foundry/iceberg/transactions
- https://www.palantir.com/docs/foundry/data-integration/branching
- https://www.palantir.com/docs/foundry/transforms-python/create-historical-dataset

**分层 / 构建 / 调度：**
- https://www.palantir.com/docs/foundry/building-pipelines/recommended-project-structure
- https://www.palantir.com/docs/foundry/building-pipelines/create-incremental-syncs
- https://www.palantir.com/docs/foundry/building-pipelines/maintaining-incremental-performance
- https://www.palantir.com/docs/foundry/building-pipelines/triggers-reference
- https://www.palantir.com/docs/foundry/data-integration/schedules

**数据期望：**
- https://www.palantir.com/docs/foundry/transforms-python/data-expectations-getting-started
- https://www.palantir.com/docs/foundry/transforms-python/data-expectations-reference

**社区实践：**
- https://medium.com/d-one/a-practical-guide-to-using-the-incremental-decorator-in-foundry-d29a1ba2264f
- https://medium.com/@ashutoshkumbhare07/mastering-palantir-incremental-streamline-your-data-workflows-444963c8f49a
- https://learn.palantir.com/dataeng-02-repositories
