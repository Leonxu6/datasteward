"""RAG vector-store persistence backed by PostgreSQL + pgvector."""
from __future__ import annotations

import psycopg2

from dm.config import (SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD, SRC_PG_PORT,
                       SRC_PG_USER)
from dm.docs.embed import DIM


def connect(autocommit=True):
    if not isinstance(autocommit, bool):
        raise ValueError("autocommit must be boolean")
    connection = psycopg2.connect(
        host=SRC_PG_HOST,
        port=SRC_PG_PORT,
        user=SRC_PG_USER,
        password=SRC_PG_PASSWORD,
        dbname=SRC_PG_DB,
        connect_timeout=15,
    )
    connection.autocommit = autocommit
    return connection


def connect_vec(autocommit=True):
    """Connect and register pgvector while avoiding leaks if registration fails."""
    from pgvector.psycopg2 import register_vector

    connection = connect(autocommit=autocommit)
    try:
        register_vector(connection)
    except Exception:
        connection.close()
        raise
    return connection


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
    """Create the vector schema idempotently and always close cursor/connection."""
    connection = connect()
    cursor = None
    try:
        cursor = connection.cursor()
        for statement in _ddl():
            cursor.execute(statement)
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def counts():
    """Return ``(document_count, chunk_count)`` with deterministic cleanup."""
    connection = connect()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT count(*) FROM document")
        document_row = cursor.fetchone()
        cursor.execute("SELECT count(*) FROM doc_chunk")
        chunk_row = cursor.fetchone()
        if not document_row or not chunk_row:
            raise RuntimeError("vector store count query returned no row")
        document_count, chunk_count = document_row[0], chunk_row[0]
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (document_count, chunk_count)):
            raise RuntimeError("vector store count query returned invalid counts")
        return document_count, chunk_count
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
