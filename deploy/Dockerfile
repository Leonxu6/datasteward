# DataSteward 应用镜像（多架构：随构建机自然产出 amd64/arm64）
# 一镜像多服务：dm-app / dm-dingtalk / dagster-webserver / dagster-daemon / dm-cli 复用同一镜像。
# 构建（在仓库根目录）：docker build -f deploy/Dockerfile -t datasteward/dm:latest .
# 国内网络可加速：docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple ...
# 嵌入模型不进镜像（运行时挂 /data/embed_cache 缓存目录）。

FROM python:3.12-slim AS builder
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
# 先拷贝依赖清单，充分利用层缓存
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel ".[rag,kg,connectors,agent,dbt,orchestration,dingtalk]" -w /wheels
# protobuf 单独出轮：dagster grpc-health gencode 7.35 需要 runtime≥7.35，但 dbt-core
# 元数据 pin <7 会让统一 resolve 无解 —— 只能装完后覆盖（DEVLOG 坑20）
RUN pip wheel "protobuf>=7.35" --no-deps -w /wheels-pb

FROM python:3.12-slim
ENV PYTHONUTF8=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DM_DATA_DIR=/data \
    DM_EMBED_CACHE=/data/embed_cache \
    HF_HUB_OFFLINE=1
# mysql 客户端库运行期不需要（pymysql 纯 Python）；tini 收割僵尸进程
RUN apt-get update && apt-get install -y --no-install-recommends tini curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /wheels /wheels
COPY --from=builder /wheels-pb /wheels-pb
RUN pip install --no-index --find-links=/wheels "datasteward[rag,kg,connectors,agent,dbt,orchestration,dingtalk]" \
    && pip install --no-index --find-links=/wheels-pb --no-deps --upgrade protobuf \
    && rm -rf /wheels /wheels-pb
WORKDIR /app
COPY transform ./transform
COPY deploy/dagster ./deploy/dagster
COPY infra ./infra
# 构建期固化 dbt manifest（dagster-dbt 加载资产图必需；parse 纯离线不连库）
RUN cd transform/dbt && dbt parse --profiles-dir . --no-partial-parse
RUN mkdir -p /data/logs
ENTRYPOINT ["tini", "--"]
CMD ["dm-app", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true"]
