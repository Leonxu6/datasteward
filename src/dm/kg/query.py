"""知识图谱查询（供 graph_query 工具）：三种受限模式，只读。

- find_related(entity_id, max_hops)：与某实体 N 跳内相连的实体 + 路径上的关系（跨域链接）。
- impact_path(entity_id, target_type)：从某实体到某类实体的最短路径（断供影响 / 溯源）。
- restricted_cypher(cypher)：只读 Cypher（写/管理关键字一律拒绝）。
"""
import re

from dm.kg.store import run_read
from dm.kg.validation import bounded_int, label_name, required_text

_WRITE = re.compile(r"\b(create|merge|delete|set|remove|detach|drop|load\s+csv|"
                    r"foreach|call\s*\{|apoc\.|dbms\.|db\.create)\b", re.I)


def find_related(entity_id: str, max_hops: int = 2, limit: int = 30):
    entity_id = required_text(entity_id, name="entity_id")
    h = bounded_int(max_hops, name="max_hops", minimum=1, maximum=4)
    lim = bounded_int(limit, name="limit", minimum=1, maximum=100)
    rows = run_read(
        f"MATCH (a {{id:$id}}) "
        f"MATCH p=(a)-[*1..{h}]-(b) WHERE b<>a "
        f"WITH b, [r IN relationships(p) | type(r)] AS rels, length(p) AS d "
        f"RETURN labels(b)[0] AS type, b.id AS id, coalesce(b.name,b.title,b.id) AS name, "
        f"b._cn AS cn, min(d) AS hops, head(collect(rels)) AS via "
        f"ORDER BY hops, type LIMIT {lim}", id=entity_id)
    return {"mode": "find_related", "entity": entity_id, "max_hops": h, "count": len(rows), "related": rows}


def impact_path(entity_id: str, target_type: str, max_hops: int = 4, limit: int = 20):
    entity_id = required_text(entity_id, name="entity_id")
    tt = label_name(target_type)
    h = bounded_int(max_hops, name="max_hops", minimum=1, maximum=6)
    lim = bounded_int(limit, name="limit", minimum=1, maximum=50)
    rows = run_read(
        f"MATCH (a {{id:$id}}) MATCH p=shortestPath((a)-[*1..{h}]-(b:{tt})) WHERE b<>a "
        f"RETURN b.id AS id, coalesce(b.name,b.title,b.id) AS name, b._cn AS cn, length(p) AS hops, "
        f"[n IN nodes(p) | labels(n)[0]+':'+coalesce(n.name,n.title,n.id)] AS path, "
        f"[r IN relationships(p) | type(r)] AS rels "
        f"ORDER BY hops LIMIT {lim}", id=entity_id)
    return {"mode": "impact_path", "entity": entity_id, "target_type": tt, "count": len(rows), "paths": rows}


def restricted_cypher(cypher: str, limit: int = 50):
    c = (cypher or "").strip().rstrip(";")
    if not c:
        return {"mode": "cypher", "error": "空查询"}
    if _WRITE.search(c):
        return {"mode": "cypher", "error": "只读：检测到写/管理关键字，已拒绝"}
    if not re.search(r"\blimit\b", c, re.I):
        c += f" LIMIT {max(1, min(int(limit), 200))}"
    rows = run_read(c)
    return {"mode": "cypher", "cypher": c, "count": len(rows), "rows": rows}
