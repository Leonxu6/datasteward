"""Bounded read-only knowledge-graph query helpers."""
from __future__ import annotations

import re

from dm.kg.store import run_read

_WRITE = re.compile(
    r"\b(create|merge|delete|set|remove|detach|drop|load\s+csv|foreach|call|apoc\.|dbms\.|db\.create)\b",
    re.I,
)
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_MAX_CYPHER_LENGTH = 20_000


def _clean_text(value: object, *, field: str, max_length: int = 512) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be non-empty unpadded text")
    if len(value) > max_length:
        raise ValueError(f"{field} must be at most {max_length} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field} contains control characters")
    return value


def _bounded_int(value: object, *, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return value


def find_related(entity_id: str, max_hops: int = 2, limit: int = 30):
    entity = _clean_text(entity_id, field="entity_id")
    hops = _bounded_int(max_hops, field="max_hops", minimum=1, maximum=4)
    row_limit = _bounded_int(limit, field="limit", minimum=1, maximum=100)
    rows = run_read(
        f"MATCH (a {{id:$id}}) "
        f"MATCH p=(a)-[*1..{hops}]-(b) WHERE b<>a "
        f"WITH b, [r IN relationships(p) | type(r)] AS rels, length(p) AS d "
        f"RETURN labels(b)[0] AS type, b.id AS id, coalesce(b.name,b.title,b.id) AS name, "
        f"b._cn AS cn, min(d) AS hops, head(collect(rels)) AS via "
        f"ORDER BY hops, type LIMIT {row_limit}",
        id=entity,
    )
    return {"mode": "find_related", "entity": entity, "max_hops": hops, "count": len(rows), "related": rows}


def impact_path(entity_id: str, target_type: str, max_hops: int = 4, limit: int = 20):
    entity = _clean_text(entity_id, field="entity_id")
    target = _clean_text(target_type, field="target_type", max_length=64)
    if not _IDENTIFIER.fullmatch(target):
        raise ValueError("target_type must be a safe graph label identifier")
    hops = _bounded_int(max_hops, field="max_hops", minimum=1, maximum=6)
    row_limit = _bounded_int(limit, field="limit", minimum=1, maximum=50)
    rows = run_read(
        f"MATCH (a {{id:$id}}) MATCH p=shortestPath((a)-[*1..{hops}]-(b:{target})) WHERE b<>a "
        f"RETURN b.id AS id, coalesce(b.name,b.title,b.id) AS name, b._cn AS cn, length(p) AS hops, "
        f"[n IN nodes(p) | labels(n)[0]+':'+coalesce(n.name,n.title,n.id)] AS path, "
        f"[r IN relationships(p) | type(r)] AS rels "
        f"ORDER BY hops LIMIT {row_limit}",
        id=entity,
    )
    return {"mode": "impact_path", "entity": entity, "target_type": target, "count": len(rows), "paths": rows}


def restricted_cypher(cypher: str, limit: int = 50):
    if not isinstance(cypher, str):
        raise ValueError("cypher must be text")
    if len(cypher) > _MAX_CYPHER_LENGTH:
        raise ValueError(f"cypher must be at most {_MAX_CYPHER_LENGTH} characters")
    if any(ord(ch) < 9 or 13 < ord(ch) < 32 or ord(ch) == 127 for ch in cypher):
        raise ValueError("cypher contains unsupported control characters")
    query = cypher.strip()
    if not query:
        return {"mode": "cypher", "error": "空查询"}
    if query.endswith(";"):
        query = query[:-1].rstrip()
    if ";" in query:
        return {"mode": "cypher", "error": "只读：一次只允许一条 Cypher 语句"}
    if _WRITE.search(query):
        return {"mode": "cypher", "error": "只读：检测到写/管理/过程调用关键字，已拒绝"}
    row_limit = _bounded_int(limit, field="limit", minimum=1, maximum=200)
    if not re.search(r"\blimit\b", query, re.I):
        query += f" LIMIT {row_limit}"
    rows = run_read(query)
    return {"mode": "cypher", "cypher": query, "count": len(rows), "rows": rows}
