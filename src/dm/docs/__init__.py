"""非结构化 RAG（S2）：合成实体挂钩文档 → 本地嵌入 → pgvector → search_documents 工具。

- generate_docs.py：合成与数仓实体（物料/供应商/订单）挂钩的文本文档（合同/SOP/质检/设备手册/规格），
  落文件 + 注册到 Postgres `document` 表（含 content-hash）。
- embed.py：本地嵌入（fastembed/onnxruntime 跑 bge-small-zh，CPU 友好；hash 后端供单测）。
- store.py：Postgres + pgvector 连接与建表（document / doc_chunk）。
- index.py：解析→切片→嵌入→写入 doc_chunk；按 content-hash 增量重建。CLI: dm-docs。
- search.py：查询向量化 → pgvector 相似检索 → 片段 + 出处（供 mcp_server.search_documents 调用）。
"""
