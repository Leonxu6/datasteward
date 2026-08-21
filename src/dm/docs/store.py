"""RAG 向量库（Postgres + pgvector）：document 注册表 + doc_chunk 向量表。

与 19 张业务 OLTP 表**同库不同表**（"一个 Postgres 一身三职"：CDC 影子源 + 向量库 + 元数据）；
Flink CDC 仅捕获 19 张业务表，doc_* 表不在其列，互不影响。
search_documents 工具直连这里做相似检索；结构化 run_sql 仍走 StarRocks。
连接参数取自 dm.config 的 SRC_PG_*（开发机经 SSH 隧道连本地 15432→主机 5432）。
"""
import psycopg2

from dm.config import (SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD, SRC_PG_PORT,
                       SRC_PG_USER)
from dm.docs.embed import DIM


def connect(autocommit=True):
    c = psycopg2.connect(host=SRC_PG_HOST, port=SRC_PG_PORT, user=SRC_PG_USER,
                         password=SRC_PG_PASSWORD, dbname=SRC_PG_DB, connect_timeout=15)
    c.autocommit = autocommit
    return c


def connect_vec(autocommit=True):
    """连接并注册 pgvector 适配，可直接传/取 Python list 作为向量。"""
    from pgvector.psycopg2 import register_vector
    c = connect(autocommit=autocommit)
    try:
        register_vector(c)
    except Exception:
        c.close()
        raise
    return c


def _ddl():
    return [
        "CREATE EXTENSION IF NOT EXISTS vector",
        """CREATE TABLE IF NOT EXISTS document (
            doc_id        VARCHAR(32) PRIMARY KEY,
            doc_type      VARCHAR(32),
            title         VARCHAR(512),
            entities      VARCHAR(512),
            source_path   VARCHAR(1024),
            content_hash  VARCHAR(64),
            indexed_hash  VARCHAR(64),
            n_chunks      INTEGER DEFAULT 0,
            created_at    TIMESTAMP DEFAULT now(),
            indexed_at    TIMESTAMP
        )""",
        f"""CREATE TABLE IF NOT EXISTS doc_chunk (
            chunk_id   VARCHAR(48) PRIMARY KEY,
            doc_id     VARCHAR(32) REFERENCES document(doc_id) ON DELETE CASCADE,
            doc_type   VARCHAR(32),
            title      VARCHAR(512),
            entities   VARCHAR(512),
            chunk_no   INTEGER,
            content    TEXT,
            embedding  vector({DIM})
        )""",
        "CREATE INDEX IF NOT EXISTS doc_chunk_emb_idx ON doc_chunk "
        "USING hnsw (embedding vector_cosine_ops)",
    ]


def init_schema():
    """建库（幂等）。注意：若改了嵌入维度 DIM，需先 DROP doc_chunk 再建。"""
    c = connect()
    cur = c.cursor()
    try:
        for stmt in _ddl():
            cur.execute(stmt)
    finally:
        cur.close()
        c.close()


def counts():
    """(文档数, 切片数)。供管理平台/CLI 观测。"""
    c = connect()
    cur = c.cursor()
    try:
        cur.execute("SELECT count(*) FROM document")
        nd = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM doc_chunk")
        nc = cur.fetchone()[0]
        return nd, nc
    finally:
        cur.close()
        c.close()
