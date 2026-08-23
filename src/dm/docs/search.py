"""向量检索（混合：稠密向量 + 实体词法加权）：查询 → pgvector 余弦近邻 → 重排 → 片段+出处。

为什么混合：多份合同/规格文本高度相似，纯语义相似度对"具体是哪个供应商/物料"（S001 vs S003）
区分力弱。这里先取较宽的向量候选，再对"查询里出现的实体 ID（S001/M0001/PA0001/CNC-08…）
命中该片段关联实体"的候选加权重排——实体专属问题稳定命中正确文档。无实体 ID 的查询 → 退化为纯向量。

供 connector/mcp_server.py 的 search_documents 工具调用（同一套审计留痕）。
"""
import re

import numpy as np

from dm.docs.embed import embed_one
from dm.docs.store import connect_vec

# 实体 ID 形态：字母前缀(1~5) + 可选连字符 + 数字(2~4)，如 S001 / M0001 / PA0001 / CNC-08 / W02
_ENTITY_RE = re.compile(r"[A-Za-z]{1,5}-?\d{2,4}")
_ENT_BONUS = 0.15      # 查询实体命中"片段关联实体"的加分
_CONTENT_BONUS = 0.05  # 仅出现在片段正文（未登记为关联实体）的较小加分
_MAX_QUERY_CHARS = 2000
_MAX_TOP_K = 100


def _entities(text):
    return {m.group(0).upper() for m in _ENTITY_RE.finditer(text or "")}


def _query_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("query must be a string")
    if not value or value != value.strip():
        raise ValueError("query must be non-empty text without surrounding whitespace")
    if len(value) > _MAX_QUERY_CHARS:
        raise ValueError(f"query must be at most {_MAX_QUERY_CHARS} characters")
    if any((ord(ch) < 32 and ch not in "\n\r\t") or ord(ch) == 127 for ch in value):
        raise ValueError("query contains unsafe control characters")
    return value


def _top_k(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("top_k must be an integer")
    if value < 1 or value > _MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {_MAX_TOP_K}")
    return value


def _query_vector(value: object) -> np.ndarray:
    try:
        vector = np.asarray(value, dtype="float32")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("query embedding must be numeric") from exc
    if vector.ndim != 1 or vector.size == 0:
        raise ValueError("query embedding must be a non-empty 1D vector")
    if not np.isfinite(vector).all():
        raise ValueError("query embedding must contain only finite values")
    return vector


def search(query: str, top_k: int = 5):
    """返回 [{doc_id, doc_type, title, entities, chunk_no, content, score, vscore}]（混合分降序）。"""
    query = _query_text(query)
    top_k = _top_k(top_k)
    qv = _query_vector(embed_one(query, is_query=True))
    q_ents = _entities(query)
    pool = max(top_k * 3, 12)
    c = connect_vec()
    cur = c.cursor()
    try:
        cur.execute(
            "SELECT doc_id, doc_type, title, entities, chunk_no, content, "
            "1 - (embedding <=> %s) AS score "
            "FROM doc_chunk ORDER BY embedding <=> %s LIMIT %s",
            (qv, qv, pool))
        rows = cur.fetchall()
    finally:
        c.close()

    out = []
    for r in rows:
        doc_ents = {e.strip().upper() for e in (r[3] or "").split(",") if e.strip()}
        content_ents = _entities(r[5])
        vscore = float(r[6])
        boost = (_ENT_BONUS * len(q_ents & doc_ents)
                 + _CONTENT_BONUS * len(q_ents & (content_ents - doc_ents)))
        out.append({"doc_id": r[0], "doc_type": r[1], "title": r[2], "entities": r[3],
                    "chunk_no": r[4], "content": r[5],
                    "score": round(vscore + boost, 4), "vscore": round(vscore, 4)})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:top_k]
