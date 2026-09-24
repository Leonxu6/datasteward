"""知识图谱（S3）：实体关系层 = 结构化 FK 骨架 + 文档抽取的新关系。

- store.py：Neo4j 连接（dm 经 SSH 隧道连 bolt 7687）+ 统计；健康检查不仅要求查询不抛错，还验证探针确实返回预期 ``ok=1``。
- build.py：① 骨架——从 StarRocks 按 schema 外键把业务行→节点、FK→语义边；
            ② 增强——claude -p 无头从文档抽 ERP 里没有的关系（设备↔物料、合同↔供应商、质检↔到货），对齐到真实实体 ID。
            CLI: dm-kg build|skeleton|extract|status|clear。
- query.py：find_related / impact_path / 受限只读 Cypher（供 graph_query 工具）；显式拒绝写入、过程调用和数据库/权限管理命令，并强制结果行数上限。
- graph_cli.py：干净子进程入口，供 connector/mcp_server.py 的 graph_query 调用（隔离 neo4j 驱动）。
"""
