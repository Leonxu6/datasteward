"""Neo4j 知识图谱连接 + 统计。dm 经 SSH 隧道连本地 7687（bolt）。

连接参数取自 dm.config 的 NEO4J_*。只读查询与写入都走同一 driver；查询侧另有白名单兜底（query.py）。
"""
from dm.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

_MAX_CYPHER_BYTES = 100_000


def _query_text(cypher: object) -> str:
    if not isinstance(cypher, str) or not cypher.strip():
        raise ValueError("cypher must be non-empty text")
    if len(cypher.encode("utf-8")) > _MAX_CYPHER_BYTES:
        raise ValueError(f"cypher must be at most {_MAX_CYPHER_BYTES} UTF-8 bytes")
    if any(ord(ch) < 9 or 13 < ord(ch) < 32 or ord(ch) == 127 for ch in cypher):
        raise ValueError("cypher contains unsupported control characters")
    return cypher


def driver():
    from neo4j import GraphDatabase
    # 关掉 driver 的 notification 噪声（如 coalesce 引用可选属性 title 时的 property-not-exist 警告）
    try:
        return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD),
                                    notifications_min_severity="OFF")
    except (TypeError, ValueError):  # 老版本驱动无此参数
        return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def run_write(cypher, **params):
    cypher = _query_text(cypher)
    drv = driver()
    try:
        with drv.session() as s:
            return s.run(cypher, **params).consume()
    finally:
        drv.close()


def run_read(cypher, **params):
    """只读查询 → list[dict]。"""
    cypher = _query_text(cypher)
    drv = driver()
    try:
        with drv.session() as s:
            return [r.data() for r in s.run(cypher, **params)]
    finally:
        drv.close()


def counts():
    """图规模：节点/边总数 + 按标签/关系类型分布。供管理平台与 dm-kg status。"""
    drv = driver()
    try:
        with drv.session() as s:
            n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            e = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            labels = {r["label"]: r["c"] for r in s.run(
                "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS c ORDER BY c DESC")}
            rels = {r["t"]: r["c"] for r in s.run(
                "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC")}
            extracted = s.run("MATCH ()-[r {source:'doc'}]->() RETURN count(r) AS c").single()["c"]
            return {"nodes": n, "edges": e, "by_label": labels, "by_rel": rels, "doc_extracted": extracted}
    finally:
        drv.close()


def ping():
    try:
        run_read("RETURN 1 AS ok")
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, str(e)
