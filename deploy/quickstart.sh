#!/usr/bin/env bash
# DataSteward 一键部署（单机，无 sudo / 无 systemd）。在仓库根目录运行：
#   bash deploy/quickstart.sh              # 全链：基建 → 初始化 → CDC → dbt → 应用层 → 冒烟
#   bash deploy/quickstart.sh --infra-only # 只起数据基建
#   bash deploy/quickstart.sh --skip-init  # 跳过初始化链（已初始化过的机器重启用）
#   附加开关：--with-sim-u8（U8 仿真源演示，x86 only）  --with-docs（RAG 文档库 + 图谱骨架）
#
# 幂等：所有初始化步骤可重复执行。Windows 用户请在 Git Bash / WSL 中运行（需 Docker Desktop）。
export MSYS_NO_PATHCONV=1   # 防 Git Bash 把 /tmp/... 参数改写成 Windows 路径
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f deploy/docker-compose.yml"
INFRA_ONLY=0; SKIP_INIT=0; WITH_SIM_U8=0; WITH_DOCS=0
for a in "$@"; do case "$a" in
  --infra-only) INFRA_ONLY=1;;
  --skip-init) SKIP_INIT=1;;
  --with-sim-u8) WITH_SIM_U8=1;;
  --with-docs) WITH_DOCS=1;;
  *) echo "未知参数：$a"; exit 2;;
esac; done

step() { echo; echo "==== $* ===="; }

# ---------- ① 前置检查 ----------
step "① 前置检查"
docker compose version >/dev/null 2>&1 || { echo "需要 Docker + docker compose v2"; exit 1; }
if [ ! -f .env ]; then
  cp .env.example .env
  echo "已生成 .env（复制自 .env.example）。"
  echo "⚠ 智能体问答需要 LLM：编辑 .env 填 DM_LLM_API_KEY（云 API），"
  echo "  或 docker compose --profile ollama up -d 后按 .env 注释切换到本地模型。数据面不依赖 LLM，可先继续。"
fi
set -a; . ./.env; set +a
mkdir -p data/logs data/embed_cache data/file_sources

# ---------- ② Flink 连接器 jar ----------
step "② 拉取 Flink CDC 连接器 jar"
( cd infra/flink-lib && bash download.sh )

# ---------- ③ 数据基建 ----------
step "③ 启动数据基建（starrocks/postgres/flink/neo4j）"
$COMPOSE up -d starrocks postgres flink-jobmanager flink-taskmanager neo4j
[ "$WITH_SIM_U8" = 1 ] && $COMPOSE --profile sim-u8 up -d sim-u8

echo "等待 StarRocks healthy（首次约 2 分钟）..."
sr_health() { docker inspect --format '{{.State.Health.Status}}' "$($COMPOSE ps -q starrocks)" 2>/dev/null || echo ""; }
for i in $(seq 1 60); do
  [ "$(sr_health)" = "healthy" ] && break
  sleep 10
done
[ "$(sr_health)" = "healthy" ] || { echo "StarRocks 未就绪，退出"; exit 1; }
echo "StarRocks 就绪。"

if [ "$INFRA_ONLY" = 1 ]; then echo "（--infra-only 完成）"; exit 0; fi

# ---------- ④ 应用镜像 ----------
step "④ 构建应用镜像（datasteward/dm:latest）"
$COMPOSE --profile app --profile tools build dm-cli

RUN="$COMPOSE run --rm --no-deps dm-cli"

if [ "$SKIP_INIT" != 1 ]; then
  # ---------- ⑤ 幂等初始化链 ----------
  step "⑤.1 StarRocks 单副本（allin1 单 BE 必需）"
  $COMPOSE exec -T starrocks mysql -h127.0.0.1 -P9030 -uroot \
    -e 'ADMIN SET FRONTEND CONFIG ("default_replication_num"="1");' || true

  step "⑤.2 建库灌数（dm-load：19 张业务表 → StarRocks）"
  $RUN dm-load

  step "⑤.3 PG 影子源 seed（CDC 源数据）+ dagster 库"
  $RUN python -m dm.sources.seed_source
  $COMPOSE exec -T postgres psql -U "${DM_SRC_PG_USER:-dm}" -d "${DM_SRC_PG_DB:-dm}" \
    -tc "SELECT 1 FROM pg_database WHERE datname='dagster'" | grep -q 1 || \
    $COMPOSE exec -T postgres psql -U "${DM_SRC_PG_USER:-dm}" -d "${DM_SRC_PG_DB:-dm}" -c "CREATE DATABASE dagster"

  step "⑤.4 提交 Flink CDC 作业（PG → StarRocks，19 表全量+增量）"
  bash infra/submit-cdc.sh cdc_all.sql || echo "⚠ CDC 提交失败（可稍后重跑 infra/submit-cdc.sh）"

  if [ "$WITH_SIM_U8" = 1 ]; then
    step "⑤.5 仿真 U8：建库灌数 + 首次全量批抽"
    $RUN python -m dm.sources.seed_u8_sim && $RUN dm-u8 full || echo "⚠ U8 仿真链失败（可选项，跳过）"
  fi

  step "⑤.6 dbt build（ODS → DWD/DWS/ADS + 质量测试）"
  $RUN bash -lc "cd /app/transform/dbt && dbt build --profiles-dir ."

  if [ "$WITH_DOCS" = 1 ]; then
    step "⑤.7 文档库 + 图谱骨架（RAG/KG，可选）"
    $RUN dm-docs build || echo "⚠ dm-docs 失败（可选项）"
    $RUN dm-kg skeleton || echo "⚠ dm-kg 失败（可选项）"
    echo "（LLM 关系抽取不自动跑：需要时 docker compose run --rm dm-cli dm-kg extract）"
  fi
fi

# ---------- ⑥ 应用层 ----------
step "⑥ 启动应用层（Streamlit + Dagster）"
$COMPOSE --profile app up -d

# ---------- ⑦ 冒烟 ----------
step "⑦ 冒烟检查"
bash deploy/smoke.sh || true

echo
echo "===== 完成 ====="
echo "治理台   : http://127.0.0.1:${DM_PORT_APP:-8501}"
echo "Dagster  : http://127.0.0.1:${DM_PORT_DAGSTER:-3070}"
echo "Flink UI : http://127.0.0.1:${DM_PORT_FLINK:-8081}"
echo
echo "试一试："
echo "  $COMPOSE run --rm dm-cli dm-agent \"物料 M0001 现在总库存多少？\"        # 预期答案含 12"
echo "  $COMPOSE run --rm dm-cli dm-eval                                        # 跑 eval 题集"
echo "  tail -5 data/logs/audit_log.jsonl                                       # 看审计留痕"
