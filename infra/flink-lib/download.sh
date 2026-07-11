#!/usr/bin/env bash
# 下载 Flink CDC 所需的两个连接器 jar 到本目录（flink-lib/）。
# docker-compose 以文件级 bind mount 把它们挂进 jobmanager/taskmanager 的 /opt/flink/lib，
# 免去自建镜像。jar 不入 git（见 .gitignore），用本脚本按需拉取并校验 sha256。
# 用法：cd infra/flink-lib && ./download.sh
set -euo pipefail
cd "$(dirname "$0")"

fetch() {
  # 镜像顺序：maven central 直连 → 阿里云镜像兜底；可用 DM_MAVEN_MIRROR 置顶自定义镜像。
  # 国内网络建议 export DM_MAVEN_MIRROR=https://maven.aliyun.com/repository/public（central 直连
  # 在部分网络会"慢速僵死"）。curl 一律带 -m 600 超时，防卡整条部署链。
  local jar="$1" path="$2" sha="$3"
  if [ -f "$jar" ] && echo "$sha  $jar" | sha256sum -c - >/dev/null 2>&1; then
    echo "✓ $jar 已存在且校验通过，跳过"
    return
  fi
  for base in ${DM_MAVEN_MIRROR:+"$DM_MAVEN_MIRROR"} "https://repo1.maven.org/maven2" "https://maven.aliyun.com/repository/public"; do
    echo "↓ 下载 $jar ← $base"
    if curl -m 600 -fSL --retry 2 -o "$jar" "$base/$path" && echo "$sha  $jar" | sha256sum -c -; then
      return
    fi
    rm -f "$jar"
  done
  if [ -n "${https_proxy:-}" ]; then
    echo "↓ 下载 $jar ← central（经代理 $https_proxy）"
    curl -m 600 -fSL --retry 2 -o "$jar" "https://repo1.maven.org/maven2/$path" && \
      echo "$sha  $jar" | sha256sum -c - && return
  fi
  echo "❌ $jar 全部下载源失败"; return 1
}

# Postgres CDC 源连接器（Ververica / Flink CDC 3.0.1，含 Debezium + pgoutput）
fetch flink-sql-connector-postgres-cdc-3.0.1.jar \
  com/ververica/flink-sql-connector-postgres-cdc/3.0.1/flink-sql-connector-postgres-cdc-3.0.1.jar \
  c484db4d2879015124e0afc021b4b9ad6f2315d3deba497a0d54a6837493b438

# StarRocks 汇连接器（Stream Load，匹配 Flink 1.18）
fetch flink-connector-starrocks-1.2.9_flink-1.18.jar \
  com/starrocks/flink-connector-starrocks/1.2.9_flink-1.18/flink-connector-starrocks-1.2.9_flink-1.18.jar \
  1eccb5dc43c42ba63fb4588260e2f27b1de3622e14a6c17fb4213145f9ca1ccf

echo "完成。两个 jar 已就位于 $(pwd)，可执行 docker compose up -d 启动 Flink。"
