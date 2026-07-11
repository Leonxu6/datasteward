#!/usr/bin/env bash
# 把 CDC 作业 SQL 提交到 Flink（dm-cdc-pg-to-starrocks 作业）。
# 作业 SQL 不通过 mount 进容器，而是 docker compose cp 拷进去再用 sql-client.sh -f 提交
# （一次性批模式，提交后即返回，作业在集群里以 RUNNING 持续跑全量+增量）。
# 用法（在仓库根目录或 infra/ 下皆可）：
#   ./submit-cdc.sh              # 默认 cdc_all.sql：全部 19 张业务表
#   ./submit-cdc.sh cdc_inv.sql  # 仅 inventory 一张表（冒烟用）
set -euo pipefail
cd "$(dirname "$0")"

SQL="${1:-cdc_all.sql}"
COMPOSE="docker compose -f ../deploy/docker-compose.yml"

[ -f "$SQL" ] || { echo "找不到 SQL 文件：$SQL"; exit 1; }

echo "提交 $SQL → flink-jobmanager ..."
$COMPOSE cp "$SQL" "flink-jobmanager:/tmp/$(basename "$SQL")"
$COMPOSE exec -T flink-jobmanager /opt/flink/bin/sql-client.sh -f "/tmp/$(basename "$SQL")"

echo
echo "已提交。查看作业状态："
echo "  $COMPOSE exec flink-jobmanager flink list   # 应见 dm-cdc-pg-to-starrocks (RUNNING)"
echo "  Flink Web UI: http://127.0.0.1:\${DM_PORT_FLINK:-8081}"
