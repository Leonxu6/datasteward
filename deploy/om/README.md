# OpenMetadata（尽力项）运行手册

启动（在仓库根目录）：
```bash
docker compose -f deploy/docker-compose.yml --profile om up -d
# 首次初始化（om-migrate 一次性容器）完成后，UI: http://<主机>:8585
```

元数据摄取（UI 里 Settings → Databases → Add Service 更直观；等价 CLI 配置如下）：
- StarRocks：类型选 **MySQL**（StarRocks 走 MySQL 协议），host `starrocks:9030`（同 docker 网络）或宿主 `127.0.0.1:9030`，user root，databases: dm, dm_dw
- Postgres：host `postgres:5432`，user dm，database dm
- dbt artifacts：Add dbt → 选 local，manifest 路径挂载 `transform/dbt/target/manifest.json`（血缘/口径入目录）

注意：OM 是重型可选件（server+MySQL+OpenSearch 三容器，额外约 6GB 内存）；平台自建的「数据目录」页
（Streamlit）已覆盖表/列/口径/Marking 检索需求，OM 供需要企业级目录时启用。
