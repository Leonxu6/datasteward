# infra · CDC 流处理作业资产

本目录存放 **Flink CDC 管道**的作业资产：连接器 jar 下载脚本、CDC 作业 SQL、提交脚本。
容器编排见 `deploy/docker-compose.yml`（Postgres / Flink / StarRocks 都在那里定义）。

## 拓扑

```
合成数据 → Postgres(源, pgvector)  ──Flink CDC(postgres-cdc → starrocks)──►  StarRocks(汇, db=dm)
            wal_level=logical            全量快照 + pgoutput 增量              主键模型, 19 张业务表
            19 个复制槽 flink_<table>     作业名 dm-cdc-pg-to-starrocks         智能体只读查询
```

- **Postgres**（服务名 `postgres`，pgvector/pg16）：业务源库，同时是 RAG 向量库。逻辑复制已开（`wal_level=logical`）。
- **Flink + Flink CDC**（服务名 `flink-jobmanager` / `flink-taskmanager`，flink:1.18）：`postgres-cdc` 源 → `starrocks` 汇，全量 + 增量。
- **StarRocks**（服务名 `starrocks`，allin1）：数仓，主键模型（为 CDC upsert 预留），`dm-load` 建表。

## 本目录文件

| 文件 | 作用 |
|------|------|
| `flink-lib/download.sh` | 拉取 2 个连接器 jar（postgres-cdc + starrocks）并校验 sha256 |
| `flink-lib/*.jar` | 连接器 jar，bind mount 进 `/opt/flink/lib`；**不入库**，按需 download |
| `cdc_all.sql` | CDC 作业：全部 19 张业务表（源表 + 汇表 + `STATEMENT SET` 一次性提交）。由 `python -m dm.pipeline.gen_flink_cdc_sql` 生成，改口径请改生成器再重新生成 |
| `cdc_inv.sql` | 同上但仅 `inventory` 一张表，冒烟用 |
| `submit-cdc.sh` | 把 SQL 提交到 Flink（`docker compose cp` + `sql-client.sh -f`） |

> jar 体积约 30MB，不进 git。Maven 坐标与 sha256 都钉在 `flink-lib/download.sh` 里。

## 启动顺序

完整链路由 `deploy/quickstart.sh` 自动执行；手动分步等价于：

```bash
# 0. 拉取 Flink 连接器 jar（首次或换机时）
cd infra/flink-lib && ./download.sh && cd ../..

# 1. 起数据 plane（starrocks + postgres + flink jm/tm + neo4j）
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml ps   # 等 starrocks/postgres 变 healthy（StarRocks 首次 ~2min）

# 2. 建 StarRocks 汇表 + 灌 Postgres 源数据
#    CDC 汇连接器只往【已存在】的表里 Stream Load，不会自动建表 —— 必须先有 19 张目标表。
docker compose -f deploy/docker-compose.yml run --rm --no-deps dm-cli dm-load
docker compose -f deploy/docker-compose.yml run --rm --no-deps dm-cli python -m dm.sources.seed_source

# 3. 提交 CDC 作业（全量快照 → 增量）
./infra/submit-cdc.sh

# 4. 验证
docker compose -f deploy/docker-compose.yml exec flink-jobmanager flink list
# 应见 dm-cdc-pg-to-starrocks (RUNNING)；源/汇行数应一致（19/19 表）
```

## CDC 作业提交方法（细节）

作业 SQL 不挂进容器，提交脚本做两步：

```bash
docker compose -f deploy/docker-compose.yml cp infra/cdc_all.sql flink-jobmanager:/tmp/cdc_all.sql
docker compose -f deploy/docker-compose.yml exec -T flink-jobmanager /opt/flink/bin/sql-client.sh -f /tmp/cdc_all.sql
```

`-f` 为一次性批模式：读完 SQL、把 `STATEMENT SET` 里 19 条 `INSERT` 作为**一个** Flink 作业提交，命令即返回；作业在集群内以 `RUNNING` 持续跑。

关键约定（写死在 SQL 里）：
- 每张源表一个复制槽 `slot.name = flink_<table>`，`decoding.plugin.name = pgoutput`，`scan.incremental.snapshot.enabled = true`。
- Debezium publication 名 `dbz_publication`（`FOR ALL TABLES`，连接器在源库首次快照时按需自动创建）。
- `pipeline.name = dm-cdc-pg-to-starrocks`，checkpoint 间隔 5s。
- 汇侧 `sink.semantic = at-least-once`（StarRocks 主键模型幂等 upsert，重复不脏数据）。

PG 侧只有 `wal_level=logical`（及 `max_wal_senders/max_replication_slots=30`）是前置条件，已写进 compose 的 `postgres.command`；复制槽与 publication 都由连接器自动建，无需手工 SQL。

> 注意：源库 `public` 下另有 `document` / `doc_chunk` 两张 pgvector RAG 表，**不在 CDC 范围**（`cdc_all.sql` 未声明），故汇侧只有 19 张业务表。

## 运维速查

```bash
COMPOSE="docker compose -f deploy/docker-compose.yml"

# CDC 作业增删查
$COMPOSE exec flink-jobmanager flink list
$COMPOSE exec flink-jobmanager flink cancel <jobId>     # 停作业（重提用 submit-cdc.sh）

# 复制槽 / publication
$COMPOSE exec postgres psql -U dm -d dm -c \
  "select slot_name, plugin, active from pg_replication_slots order by slot_name;"

# 全部停 / 起（数据卷保留）
$COMPOSE down
$COMPOSE up -d
```

> StarRocks allin1 的 `entrypoint` 会把 FE/BE 的 `priority_networks` 改成容器子网 IP，
> 否则跨容器 Stream Load 会被重定向到不可达的 `127.0.0.1:8040`——详见 compose 内注释。
