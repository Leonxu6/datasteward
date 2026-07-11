# 07 · 数据健康与监控（Data Health）

> **一句话定位**：Data Health 是一套"给每张表/每条作业挂检查、超阈值就告警、失败自动开单、恢复自动关单"的可观测层——回答用户最关心的"到底监控些什么"。对应我们平台的落点：新建 `dm/health/` 规则引擎 + 接现有同步监控页（Flink lag / 复制槽 / 源汇对账），让"数据顿挫"被自动发觉并可回放。

---

## 一、解决什么问题（第一性原理）

数据平台的价值建立在一个隐含前提上：**下游看到的数据是可信的**。可信 = 新鲜（不是三天前的）+ 结构对（列没被悄悄改）+ 内容合理（主键唯一、数量非负、枚举合法）+ 作业跑通了（构建没静默失败）。一旦这个前提破裂，坏数据会沿血缘一路污染报表、智能体回答、决策——而且往往**无声无息**，等业务方发现时已经晚了。

Data Health 要解决的就是这一件事：**把"数据坏了"从人工偶然发现，变成机器主动、及时、分级发觉，并留下可回放的证据链**。它围绕三个第一性目标展开：

1. **早发现**：坏数据在进入下游之前（构建期门禁）或刚落库之后（新鲜度/内容检查）就被拦截或告警，而不是等报表出错。
2. **可分级**：不是所有异常都同等紧急——区分"值班要立刻起床（Critical）"和"记一笔明天看（Moderate/Warning）"，避免告警疲劳。
3. **可追溯**：每次检查的实测值、阈值、触发它的 build/事务、连续失败次数都落成追加式记录，支持事后"数据什么时候开始坏的"回放，并能沿血缘反查上游根因。

---

## 二、Palantir 怎么做（机制）

Foundry 的数据健康是**两层 + 一门禁**的协作架构：

```
                    ┌─────────────────────────────────────────┐
   构建期门禁       │  Data Expectations（Python transform 内） │  脏数据进不了下游
   （abort 级）     │  Check(expr, on_error='FAIL'|'WARN')      │  FAIL→回滚构建
                    └─────────────────────────────────────────┘
                    ┌─────────────────────────────────────────┐
   细粒度检查       │  Health Checks（挂在单个资源上）          │  5 大类 ≈ 25 种
   （落库后）       │  Status/Time/Size/Content/Schema          │  Dataset/表/Schedule/Sync
                    └─────────────────────────────────────────┘
                    ┌─────────────────────────────────────────┐
   规模化监控       │  Monitoring Views（按 scope 批量套规则）  │  运行面健康
   （运行面）       │  schedule/stream/function/agent/…         │  Folder/Project/Lineage/OSDK
                    └─────────────────────────────────────────┘
```

### 2.1 Health Checks——四类（实为五类）细粒度检查

挂在**单个资源**（Dataset / Iceberg 表 / Virtual table / Schedule / Sync 目标）上，在 Dataset Preview 的 **Health 标签页**增删改查看历史，也在 Data Lineage 里经 **Metrics > Health** 呈现。研究口径常称"四类（freshness / schema / content / expectations）"，Foundry 官方目录实为**五大类 ≈ 25 种**：

- **Status**（作业/构建/同步是否成功）
- **Time**（时长与新鲜度 freshness）
- **Size**（行数/文件数/分区小文件）
- **Content**（值分布、正则、跨表关系）
- **Schema**（结构契约）

> 术语澄清：用户口中的 "freshness" 属于 **Time 类**；"content" 与 "schema" 各自独立成类；"expectations" 指下面第 2.3 的**构建期门禁**（另一机制），而非 Health Check 的一类。四类目录完整字段见【第三节 监控目录】。

### 2.2 Monitoring Views——运行面（build health）规模化监控

一个 monitoring view = "**a collection of monitoring rules and health checks**"，按 **scope** 批量套用，避免逐资源手配：

- **static scope**：手选具体资源。
- **dynamic scope**：随资源增删自动更新——**Folder / Project / Workflow Lineage / Workshop / OSDK application**。

覆盖的运行面（build health / 资源与查询性能）包括：**schedule（调度）、stream（流）、function（函数）、action（动作）、live-deployment（在线部署）、agent（计算节点）、object & link（对象/关系）、automation（自动化）**。关键 rule 的默认严重级阈值见【第三节】表 B。

### 2.3 Data Expectations——构建期门禁（abort 级）

在 Python transform 里用 `Check(expectation, 'name', on_error='FAIL'|'WARN')` 声明断言，挂在 transform 的 Input/Output 上：

- `on_error='FAIL'`（**默认**）→ **abort 构建**，脏数据**不落下游**（基于 Dataset 单事务回滚）。
- `on_error='WARN'` → 放行但记警告。

Pipeline Builder（无代码）目前 UI 内建 **primary key + row count** 两种 expectation，publish 后**自动转为对应 health check**。这是"质量断言变成硬门禁"的机制，也是我们平台最大的能力缺口（见第四节）。

### 2.4 异常带（自适应基线告警）

Foundry 数值检查**不用真标准差**（对 build 离群值太敏感），而用 **Median Absolute Deviation (MAD)**：

```
σ ≈ MAD × 1.4826        （MAD = 各值到中位数的绝对偏差的中位数）
```

配置 = "允许偏离几个 σ" + "采样最近多少个 build 作基线"，实现**自适应基线告警**，例如"行数偏离近 30 次 build 的中位数 >3σ 即告警"。多数数值检查（Row Count / Build Duration / TSLU / Null% …）都支持这个 **Median deviation** 选项。

### 2.5 告警形态——评估触发 / 严重级 / 渠道 / issue

**严重级枚举**（两套，勿混）：

| 场景 | 枚举 |
|---|---|
| Health check | **Moderate \| Critical** |
| Monitoring rule alert | **Low \| Medium \| High** |

**评估触发模式**：
- `Automatic`：dataset 更新时 / 到时间阈值时触发；触发后把"当前时间 + 阈值"设为下次门限。
- `Custom Schedule`：固定 minute / hourly / daily / weekly / cron 跑，**无论是否构建**。

**告警渠道**：
- **站内通知**：**永远**发给失败检查的 watcher（不可关）。
- **邮件**：Settings > Notifications 里 **opt-in**。
- **PagerDuty / Slack / Webhook(REST)**：在 **monitoring view 级**配置（Manage subscriptions / Manage monitors 页设 severity 门限、snooze 时长 + 原因）。

**watch / 订阅**：单检查 `Watch` / 整 dataset `Watch All`；订阅级别枚举 **Nothing \| All failures（Moderate+Critical）\| Only critical**。

**issue（告警自动开单/关单）**：勾选 "Automatically create an issue when this check fails"，可指定 assignee；**检查恢复后自动关闭 issue**。

**escalate（升级）**：`Escalate` 选 "Add time"，设"连续失败达到某时长/次数"后**自动升级为 Critical**。

### 2.6 告警历史看板

- **Data Health 列表页**：可**按 status 或 name 过滤/排序**，可切"只看我 watch 的"。
- **检查历史**：单检查一条时间轴——每次评估的 pass/fail + 实测值 + 触发它的 build / transaction id，这是"数据顿挫回放"的原始素材。
- **未关闭 issue 面板**：issue 标题 · assignee · 开启时间 · 关联的失败检查。

---

## 三、监控目录（重点）

**本文最大价值**。以下逐项列出"**检查类型 → 信号 → 阈值/参数 → 告警形态**"。硬细节（操作符枚举、参数名、默认阈值）照留。

### 表 A · Health Checks 目录（5 类 ≈ 25 种，挂在单资源上）

**通用参数**（几乎每个检查都有）：`Severity`（**Moderate \| Critical**，必填）、`Escalate`（连续失败 N 次升级 Critical）、`Notes`、`Issues`（失败自动开、恢复自动关）。
**阈值操作符枚举**：`Between \| ≥ \| ≤ \| =`。多数数值检查支持 **Median deviation**（MAD 异常带）。

#### A. Status 类（构建/作业/同步是否成功）

| 检查类型 | 适用资源 | 信号（校验什么） | 关键参数 / 阈值 | 触发时机 |
|---|---|---|---|---|
| **Job Status** | Dataset / Iceberg / Virtual | 该 dataset 最近一次 job 成功 | — | 每次该 dataset 构建（即使下游失败，本表成功即 pass） |
| **Build Status** | Dataset / Iceberg / Virtual | 最近一次 build 成功 | — | 同一 build 内的中间 dataset 不更新其 build status |
| **Schedule Status** | Dataset | 最近一次 schedule build（含所有中间产物）成功 | — | 仅该 schedule 运行时 |
| **Sync Status** | Dataset | 到外部库的 sync 是否成功 | `Sync destination`（如 `phonograph2-cache-worker`、`jdbc-worker`，必填） | sync 时 |

#### B. Time 类（时长 / 新鲜度 freshness）

| 检查类型 | 信号（公式） | 关键参数 / 阈值 | 备注 |
|---|---|---|---|
| **Build Duration** | 单次 build 耗时 | `Build duration`(days/min/hours) + 操作符；可选 Median deviation（σ 数、采样 build 数） | 仅对 build 终端输出更新 |
| **Sync Duration** | 单次 sync 耗时 | `Sync destination` + `Sync duration` + 操作符 + Median deviation | — |
| **Time Since Last Updated (TSLU)** | `当前时间 − 最近事务提交时间` | `Last updated`(时间单位)+操作符；`Ignore empty transactions`(Y/N,必填)；`Schedule`(**Automatic\|Custom**,必填)；Median deviation | 例："TSLU < 1 hour，超时即 fail" |
| **Time Since Sync Last Updated** | `当前时间 − 最近 sync 时间` | `Last sync` + 操作符 + Median deviation | — |
| **Data Freshness** | `最近事务提交时间 − 某时间戳列的最大值` | `Column name`(必填) + `Freshness range` + 操作符 | 仅有事务提交时触发 |
| **Sync Freshness** | `最近 sync 时间 − 某 datetime 列最大值` | `Column name` + `Freshness range` + 操作符 | — |

#### C. Size 类（行数 / 文件）

| 检查类型 | 信号 | 关键参数 / 阈值 |
|---|---|---|
| **Row Count** | 行数 | `Row count` + 操作符 + Median deviation；可对比上次成功检查值 |
| **Dataset File Count** / **Transaction File Count** | 文件数 | 文件数 + 操作符 + Median deviation |
| **Transaction File Size** | 事务文件大小 | MB/KB + 操作符 + Median deviation |
| **Dataset Partition**（小文件治理，无配置） | 小文件比例 | `<50 文件` 即 pass；`≥50 文件` 时需 **≥90% 文件 >96MB** 才 pass |

#### D. Content 类（值分布 / 正则 / 关系）

| 检查类型 | 信号 | 关键参数 / 阈值 |
|---|---|---|
| **Primary Key** | 该列 100% 唯一且非空 | `Column name` |
| **Null Percentage** | 空值占比 | `Column name` + `Null %` + 操作符 + Median deviation |
| **Allowed Column Values** | 值落在白名单内 | `Column name` + `Allowed values`（逗号分隔） |
| **Numeric Range** | 值落在数值域 | `Column name` + `Allowed range`（`min-max`） |
| **Numeric Mean** / **Numeric Median** | 均值/中位数 | 值 + 操作符 + `Difference from last check`（相对上次偏移） |
| **Approximate Unique Percentage** | 近似基数占比 | 占比 + 操作符 |
| **Column Regex** | 列值匹配正则 | `Column name` + `Regex`（如 `^Pre`、`post$`、`.*any.*`） |
| **Date Range** | 日期落在区间 | `Column name` + `Allowed date range`（`YYYY-MM-DD – YYYY-MM-DD`） |
| **Approximate Column Relation** | 跨数据集列相似度（≈ 外键/对账） | `Other dataset path` + `Column1`(源) + `Column2`(目标) + `% match` |

#### E. Schema 类（结构契约）

| 检查类型 | 信号 | 关键参数 / 阈值 |
|---|---|---|
| **Column** | 某列存在且类型对 | `Column name` + `Is Present`(Y) + `Type`（如 Integer/String） |
| **Column Count** | 列数 | 列数（数值） |
| **Schema** | 整体结构契约 | `Columns`（列名+类型）+ `Comparison type`（四枚举，见下） |

**Schema `Comparison type` 四枚举**：

| 枚举 | 含义 |
|---|---|
| `EXACT_MATCH_ORDERED_COLUMNS` | 列序 + 名 + 类型 + 数**全一致** |
| `EXACT_MATCH_UNORDERED_COLUMNS` | 名 + 类型 + 数一致，**忽略序** |
| `COLUMN_ADDITIONS_ALLOWED` | **可新增列**，既有列必须在（推荐默认） |
| `COLUMN_ADDITIONS_ALLOWED_STRICT` | 新增后既有列**锁定** |

### 表 B · Monitoring Rules 目录（运行面 / build health，带默认严重级阈值）

alert severity 枚举 **Low \| Medium \| High**。

| 资源面 | Rule | 信号 | 默认阈值 → 严重级 |
|---|---|---|---|
| **Schedule** | Consecutive schedule failures（排除 cancelled） | 连续失败次数 | **≥1 Medium，≥3 High** |
| | Schedule duration | 单次调度耗时 | ≥2h |
| **Dataset** | Time since job last succeeded | 距上次成功 | >1 day（推荐） |
| **Stream（derived）** | Total lag | 未处理上游记录数 | >1000 |
| | Liveness: time since last successful checkpoint | 距上次成功 checkpoint | ≥2min |
| | Last checkpoint duration | 单次 checkpoint 耗时 | >10min |
| | Total throughput | 吞吐 | <100 |
| **Stream（ingest）** | Records ingested over last 5/30min/1h/4h/1d | 时窗摄入量 | ≤100 |
| **Object / Link** | Sync jobs failing | 同步失败数 | **≥1 Low / ≥3 Medium / ≥7 High** |
| | Invalid stream records detected（格式违规） | 违规记录数 | **不可配，≥1 即 Critical** |
| | Sync propagation delay | 传播延迟 | ≥1day |
| **Function / Action** | … duration p95 | p95 时延 | >10s |
| | Number of … failures in window | 窗口内失败数 | >0，窗口 1h（区分 user-facing / non-user-facing） |
| **Live deployment** | Live deployment heartbeat | 心跳 | ≥1min |
| **Agent（计算节点）** | High CPU utilization | CPU | >80% |
| | JVM heap usage | 堆占用 | >70% |
| | Low disk space | 剩余磁盘 | <10GB |
| | Queue size | 排队作业 | >70 jobs |
| | 证书到期 | 剩余天数 | **<30d Medium，<10d High** |
| | 心跳/版本陈旧 | 空闲时长 | >10min / >10day |
| **Automation** | disabled by the system | 被系统禁用 | **不可配 High** |
| | repeated execution/evaluation failures in window | 窗口内重复失败 | >0，窗口 1h |

### 3.1 一个"生产数据集监控页"应显示的 KPI

照抄 Foundry Health 标签页 + Data Health 表。单数据集监控页应含下列 KPI：

| 分区 | KPI 字段 | 取值/形态 |
|---|---|---|
| 概览 | **聚合健康状态** | Healthy / Failing（有 Critical 失败）/ Warning（仅 Moderate 失败）——由该表所有检查**取最严** |
| 概览 | **Last build / Last job status** | Succeeded / Failed + 时间戳 |
| 概览 | **Freshness** | TSLU 值 vs 阈值（如 "12min / <1h ✓"） |
| 概览 | **Row count** | 当前值 + 与基线偏差（MAD σ 数） |
| 检查清单 | **每检查一行** | 检查名 · 类别 · 状态(Passing/Failing) · 严重级(Moderate/Critical) · 阈值 · 实测值 · 上次评估时间 · watch |
| 历史 | **检查历史** | 时间轴：每次评估的 pass/fail + 实测值 + 触发的 build/transaction id |
| 告警 | **未关闭 issue** | issue 标题 · assignee · 开启时间 · 关联失败检查 |
| 血缘 | **上游健康** | 直接上游 dataset 的健康状态（红/黄/绿），供反向溯源 |

---

## 四、映射到DataSteward 栈（我们怎么复刻）

**总体架构**：新建 `dm/health/` 模块 = **registry**（JSON check 定义）+ **evaluator**（定时跑，写 JSONL 结果）+ **notifier**（钉钉/邮件/站内）+ 一个 `dm.connector.mcp_server` 只读工具 `health_status(resource)` 供智能体查。Streamlit 治理台加"**数据健康**"页读结果 JSONL 渲染上面的 KPI。**已有 `dm/pipeline/health.py` 的 `cdc_reconcile()` / `replication_slots()` 直接升级为其中两个 evaluator**——这就是"接现有同步监控页（Flink lag / 复制槽 / 源汇对账）"的落点。

### 4.1 逐机制映射表

| Foundry 机制 | 我方复刻（StarRocks / PG / Flink CDC / Neo4j / pgvector / 只读 MCP + JSONL 审计 / 无头 Claude / Streamlit） | 现状/落点 |
|---|---|---|
| **Health check registry** | `dm/health/checks/*.json`（见 4.2 schema）；`schema.py` 19 表驱动默认套装 | 新增；schema.py 已是 single source |
| **Status: Job/Build Status** | Flink/dbt/dm-load 作业退出码 + 时间戳写 `logs/build_status.jsonl` | 新增薄封装 |
| **Time: TSLU** | SQL `now() − max(_committed_at)` 或表级 `SELECT max(updated_at)`（StarRocks 侧算） | 直接实现 |
| **Time: Data/Sync Freshness** | StarRocks 落库表 `now()−max(updated_at)`；CDC sync 后写 sync 时间戳 | 直接实现 |
| **Time: Build/Sync Duration** | 作业起止差 + MAD 基线（从历史 JSONL 算） | 新增 |
| **Size: Row Count(+MAD)** | `SELECT count(*)`；MAD 从最近 N 次结果 JSONL 现算 | 直接实现 |
| **Size: 小文件/Partition** | StarRocks tablet/compaction 指标；PoC 可略 | 可延后 |
| **Content: Primary Key** | `count(*)=count(distinct pk) AND sum(pk is null)=0` | 直接实现 |
| **Content: Null%/Range/Regex/Allowed/Mean/Median** | 纯 SQL 聚合（StarRocks 侧算，只读 MCP 执行） | 直接实现 |
| **Content: Approx Column Relation** | 即我方 `cdc_reconcile()` 源(PG)汇(StarRocks)对账，升级为"外键覆盖率/行数比" | **已有雏形**，升级 |
| **Schema 类 + Comparison enum** | `schema.py` 期望结构 vs `information_schema.columns` 实测；实现 4 枚举比对（默认 `COLUMN_ADDITIONS_ALLOWED`） | 新增，schema.py 已备料 |
| **Data Expectations 构建期 abort** | Flink 落库前/dbt test 处执行断言，失败即中断该表写入（事务/分区级）= FAIL；WARN 只记 JSONL | **最大新增点**：断言前移成门禁 |
| **Monitoring rule: schedule/stream/agent** | 调度器连续失败计数 + Flink checkpoint/lag（Flink REST `/jobs/<id>/checkpoints`）+ 主机 CPU/磁盘（node_exporter/psutil） | Flink 已在主机 compose；补采集 |
| **异常带 MAD** | evaluator 内 `median + 1.4826×MAD×sigmas` 现算 | 纯计算，直接实现 |
| **评估触发 Automatic/Custom** | evaluator 由 cron(custom) 或落库钩子(automatic)触发 | 直接实现 |
| **告警渠道 + level 枚举** | notifier：站内(治理台内消息)恒发；`dm-dingtalk push` 作 webhook；level(nothing/all/only_critical) 过滤 | **钉钉已有**，接线即可 |
| **issue 自动开/关** | 结果 JSONL 里维护 issue 记录，恢复自动置 closed；治理台展示 | 新增轻量实现 |
| **severity 枚举** | 沿用 Moderate/Critical(check) + Low/Med/High(rule) | 直接采用 |
| **watch/订阅** | 治理台按用户存 watch 列表 | 新增 |
| **Data Health dashboard KPI** | Streamlit "数据健康"页 = 3.1 的 KPI 表 | 新增页 |
| **血缘联动健康（反向溯源）** | Neo4j 图节点挂 health 状态属性，下游异常沿边反查上游红点 | Neo4j 图已有(S3)，加属性 |
| **只读 + 审计一致性** | 所有检查 SQL 走只读 MCP，评估动作写 `audit_log.jsonl`，`session_id` 关联 | 复用现有审计骨架 |

### 4.2 可直接落地的 JSON check 定义（registry schema 建议）

```json
{
  "check_id": "chk_dwd_sales_order_freshness",
  "resource": {"kind": "starrocks_table", "name": "dwd.sales_order"},
  "category": "time",
  "type": "time_since_last_updated",
  "params": {
    "operator": "lte",           // between|gte|lte|eq
    "value": 60, "unit": "minutes",
    "ignore_empty_transactions": true,
    "median_deviation": {"sigmas": 3, "sample_builds": 30}
  },
  "severity": "critical",         // moderate|critical
  "escalate": {"after_consecutive_failures": 3},
  "schedule": {"mode": "custom", "cron": "*/10 * * * *"},  // 或 mode=automatic
  "notify": {"in_platform": true, "email": true,
             "webhook": "dingtalk", "level": "all_failures"}, // nothing|all_failures|only_critical
  "issue": {"auto_create": true, "auto_close": true, "assignee": "data-oncall"},
  "notes": "销售明细需每 10 分钟内有新事务"
}
```

### 4.3 检查结果记录（JSONL，对齐我方追加式审计）

```json
{"ts":"2026-07-01T09:10:00+08:00","check_id":"chk_dwd_sales_order_freshness",
 "resource":"dwd.sales_order","status":"failing","severity":"critical",
 "observed":{"tslu_minutes":95},"threshold":{"op":"lte","value":60,"unit":"minutes"},
 "consecutive_failures":2,"baseline":{"median":8,"mad":3,"sigmas_out":29},
 "triggered_by":{"build_id":null,"eval_mode":"custom_schedule"},
 "session_id":"health-2026-07-01","issue_id":"iss_812"}
```

> **"数据顿挫如何被发觉并回放"**：某表停止更新 → evaluator 的 TSLU 检查在下一个 cron 周期算出 `tslu_minutes=95 > 60` → status 置 `failing`、severity `critical`、`consecutive_failures` 自增 → notifier 按 level 发钉钉/站内 → 自动开 issue（`issue_id`）。**回放**：治理台按 `resource` 拉这张表的全部 JSONL，时间轴上 `status` 从 `passing→failing` 的第一条 `ts` 就是"数据什么时候开始顿挫"的准确锚点；`triggered_by` 关联到具体 build/事务。恢复后下一次评估 `status=passing`，issue 自动置 `closed`。

### 4.4 构建期门禁（我方 Flink 落库后 / dbt test 处照抄）

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
    Check(E.schema(), "结构契约", on_error="FAIL"),  # 附列+类型
  ]))
def compute(...): ...
```

> Foundry 期望 API 谓词参考：列级 `E.col('c')` → `.non_null()/.gt()/.gte()/.lt()/.lte()/.equals()/.between()`；聚合 `.null_count()/.null_percentage()/.distinct_count()/.sum()`；组合 `E.all(...)`；数据集级 `E.primary_key('a','b')/E.count()/E.group_by(...)/E.schema()`。我方在 Flink sink 前或 dbt test 处执行同等断言，FAIL 即中断该表写入（倾向 staging→swap 事务/分区级）。

### 4.5 我方 19 表默认监控套装

每个生产落库表**至少**挂：

- **Job Status**（critical）
- **TSLU**（critical，按表频率设阈值）
- **Row Count**（moderate，带 MAD）
- **Primary Key**（critical）
- **Schema = `COLUMN_ADDITIONS_ALLOWED`**（critical）

**CDC 链路额外挂**：

- 源汇行数 `Approximate Column Relation` / reconcile（critical，即升级后的 `cdc_reconcile()`）
- Sync Freshness（基于 `updated_at` 列）
- Flink 流 `Total lag` > 1000 / `Liveness` ≥ 2min（接现有同步监控页）

**Schedule 挂**：`Consecutive schedule failures`（≥1 Medium / ≥3 High）。

### 4.6 落地路线（一句话）

① `registry + evaluator + JSONL 结果` → ② `默认套装（Job/TSLU/RowCount+MAD/PK/Schema）挂满 19 表` → ③ `把 reconcile 升级为构建期 abort 门禁（FAIL/WARN）` → ④ `钉钉/站内 notifier + issue 开关` → ⑤ `Streamlit 健康页 + Neo4j 图挂健康属性做反向溯源`。**前四步纯用现有能力即可交付。**

---

## 五、Open questions

1. **构建期 abort 的事务粒度**：Foundry abort 基于 Dataset 单事务回滚；我方 StarRocks/Flink sink 无等价"整 build 单事务"，需实测能否用 Stream Load 事务/分区 swap 实现"断言失败不切分区"，倾向 **staging→swap** 模式。
2. **MAD 基线冷启动**：历史 JSONL 样本不足时前 N 次是否只 warn、样本阈值（<10 次不启用异常带）待定。
3. **Custom Schedule 最小粒度**：evaluator 用 cron 还是常驻；分钟级 freshness 对 StarRocks 只读查询压力（19 表 × 多检查 × 每分钟）需实测。
4. **Approximate 类算法**：StarRocks 有 `approx_count_distinct`(HLL)，但跨表列相似度无内建，需自研或降级为精确对账，阈值待定。
5. **告警去抖**：多表同时 freshness fail 会告警风暴，是否按血缘上游根因聚合（Neo4j 可支撑）规则待设计。
6. **官方 status 完整英文枚举**：Passing/Failing 之外是否有 Stale / In progress / Not run，以及结果对象字段未逐字取到（docs 为 SPA），严格对齐需登录实例抓 API。
7. **Schema 类型三方映射**：Foundry `Integer/String` vs StarRocks `TINYINT/VARCHAR` vs PG 源类型需固化，避免误报。
8. **Monitoring View scope**：我方无 Workflow Lineage / OSDK 对应，简化为 Project / Folder / Single；是否需"按血缘子图"动态 scope 待定。

---

## 六、来源

**Health Checks（检查类型 / 参考 / 概览 / 评估 / watch / 通知）**
- https://www.palantir.com/docs/foundry/health-checks/check-types
- https://www.palantir.com/docs/foundry/health-checks/checks-reference
- https://www.palantir.com/docs/foundry/data-health/checks-reference
- https://www.palantir.com/docs/foundry/health-checks/overview
- https://www.palantir.com/docs/foundry/health-checks/check-evaluation
- https://www.palantir.com/docs/foundry/data-health/check-evaluation
- https://www.palantir.com/docs/foundry/health-checks/watching-checks
- https://www.palantir.com/docs/foundry/health-checks/notifications
- https://www.palantir.com/docs/foundry/data-integration/health-checks
- https://www.palantir.com/docs/foundry/maintaining-pipelines/recommended-health-checks

**Data Expectations（构建期门禁）**
- https://www.palantir.com/docs/foundry/maintaining-pipelines/define-data-expectations
- https://www.palantir.com/docs/foundry/transforms-python/data-expectations-reference
- https://www.palantir.com/docs/foundry/transforms-python/data-expectations-getting-started
- https://www.palantir.com/docs/foundry/pipeline-builder/dataexpectations-overview
- https://www.palantir.com/docs/foundry/pipeline-builder/dataexpectations-configure-health-check
- https://community.palantir.com/t/can-data-expectations-be-set-to-warn-instead-of-fail/904

**Data Health & Monitoring Views（运行面 / 规模化）**
- https://www.palantir.com/docs/foundry/observability/data-health
- https://www.palantir.com/docs/foundry/data-health/overview
- https://www.palantir.com/docs/foundry/monitoring-views/overview
- https://www.palantir.com/docs/foundry/monitoring-views/rules-reference
- https://www.palantir.com/docs/foundry/monitoring-views/core-concepts
