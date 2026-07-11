#!/usr/bin/env bash
# 部署冒烟：每项打 ✅/❌，最后汇总。只读检查，不改任何状态（最后的 dm-agent 会留一条审计——预期行为）。
# 在仓库根目录运行：bash deploy/smoke.sh
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE="docker compose -f deploy/docker-compose.yml"
WH_DB="${DM_WH_DB:-dm}"
DW_SCHEMA="${DM_DW_SCHEMA:-dm_dw}"
PORT_FLINK="${DM_PORT_FLINK:-8081}"
PORT_APP="${DM_PORT_APP:-8501}"
PORT_DAGSTER="${DM_PORT_DAGSTER:-3070}"
PORT_NEO4J_BOLT="${DM_PORT_NEO4J_BOLT:-7687}"

PASS=0; FAIL=0
ck() {  # ck <名称> <命令...>
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "✅ $name"; PASS=$((PASS+1)); else echo "❌ $name"; FAIL=$((FAIL+1)); fi
}
sr() { $COMPOSE exec -T starrocks mysql -h127.0.0.1 -P9030 -uroot -N -e "$1" 2>/dev/null; }

echo "===== smoke ====="
ck "StarRocks SELECT 1" $COMPOSE exec -T starrocks mysql -h127.0.0.1 -P9030 -uroot -e "SELECT 1"
N19=$(sr "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$WH_DB' AND table_name NOT LIKE 'raw_u8__%'" | tr -d '[:space:]')
[ "${N19:-0}" -ge 19 ] && { echo "✅ 业务表数量 $N19 (>=19)"; PASS=$((PASS+1)); } || { echo "❌ 业务表数量 ${N19:-0} (<19)"; FAIL=$((FAIL+1)); }
NROWS=$(sr "SELECT COUNT(*) FROM $WH_DB.material" | tr -d '[:space:]')
[ "${NROWS:-0}" -gt 0 ] && { echo "✅ material 行数 $NROWS"; PASS=$((PASS+1)); } || { echo "❌ material 空"; FAIL=$((FAIL+1)); }
NADS=$(sr "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DW_SCHEMA' AND table_name LIKE 'ads_%'" | tr -d '[:space:]')
[ "${NADS:-0}" -ge 3 ] && { echo "✅ ADS 宽表数 $NADS"; PASS=$((PASS+1)); } || { echo "❌ ADS 宽表数 ${NADS:-0} (<3)"; FAIL=$((FAIL+1)); }
RUNNING=$(curl -s "http://127.0.0.1:$PORT_FLINK/jobs/overview" | python3 -c "import sys,json;print(sum(1 for j in json.load(sys.stdin).get('jobs',[]) if j['state']=='RUNNING'))" 2>/dev/null || echo 0)
[ "${RUNNING:-0}" -ge 1 ] && { echo "✅ Flink RUNNING 作业 $RUNNING"; PASS=$((PASS+1)); } || { echo "❌ Flink 无 RUNNING 作业"; FAIL=$((FAIL+1)); }
ck "Neo4j bolt 端口" bash -c "</dev/tcp/127.0.0.1/$PORT_NEO4J_BOLT"
# 可选：U8 仿真源（--profile sim-u8 启用时才检查）
if $COMPOSE ps --status running sim-u8 2>/dev/null | grep -q sim-u8; then
  ck "仿真 U8 TDS 可达" bash -c "</dev/tcp/127.0.0.1/${DM_PORT_MSSQL:-11433}"
fi
# 可选：LLM 端点（未配置则跳过）。本脚本在宿主跑：容器视角域名改写为宿主可达地址
if [ -n "${DM_LLM_BASE_URL:-}" ]; then
  LLM_URL="${DM_LLM_BASE_URL/host.docker.internal/127.0.0.1}"
  LLM_URL="${LLM_URL/\/\/ollama:/\/\/127.0.0.1:}"
  ck "LLM 端点 /models" curl -sf -H "Authorization: Bearer ${DM_LLM_API_KEY:-sk-local}" "${LLM_URL%/}/models"
fi
ck "Streamlit $PORT_APP" curl -sf "http://127.0.0.1:$PORT_APP/_stcore/health"
# Dagster webserver 冷启动约 1 分钟（加载 dbt manifest + 43 资产）——带重试
dagster_up() { for i in 1 2 3 4 5 6; do curl -sf "http://127.0.0.1:$PORT_DAGSTER/server_info" >/dev/null 2>&1 && return 0; sleep 10; done; return 1; }
ck "Dagster $PORT_DAGSTER" dagster_up
AUD_BEFORE=$(wc -l < ./data/logs/audit_log.jsonl 2>/dev/null || echo 0)
if $COMPOSE run --rm --no-deps dm-cli dm-agent "物料 M0001 现在总库存多少？" 2>/dev/null | grep -q "12"; then
  echo "✅ 智能体 E2E（M0001=12）"; PASS=$((PASS+1))
else
  echo "❌ 智能体 E2E"; FAIL=$((FAIL+1))
fi
AUD_AFTER=$(wc -l < ./data/logs/audit_log.jsonl 2>/dev/null || echo 0)
[ "${AUD_AFTER:-0}" -gt "${AUD_BEFORE:-0}" ] && { echo "✅ 审计新增 $((AUD_AFTER-AUD_BEFORE)) 条"; PASS=$((PASS+1)); } || { echo "❌ 审计未新增"; FAIL=$((FAIL+1)); }
echo "===== smoke 结果：$PASS 过 / $FAIL 挂 ====="
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
