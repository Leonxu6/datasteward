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


def _nonnegative_count(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"graph statistics returned invalid {field}")
    return value


def _single_count(record: object, *, field: str) -> int:
    if record is None:
        raise RuntimeError(f"graph statistics returned no {field} row")
    try:
        value = record["c"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"graph statistics returned malformed {field} row") from exc
    return _nonnegative_count(value, field=field)


def _distribution(records, *, key: str, field: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for record in records:
        try:
            name = record[key]
            count = record["c"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"graph statistics returned malformed {field} row") from exc
        if not isinstance(name, str) or not name or name != name.strip():
            raise RuntimeError(f"graph statistics returned invalid {field} name")
        if name in result:
            raise RuntimeError(f"graph statistics returned duplicate {field} name: {name}")
        result[name] = _nonnegative_count(count, field=f"{field} count")
    return result


def driver():
    from neo4j import GraphDatabase
    # 关掉 driver 的 notification 噪声（如 coalesce 引用可选属性 title 时的 property-not-exist 警告）
    try:
        return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD),
                                    notifications_min_severity="OFF")
    except TypeError:  # 老版本驱动无此参数
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
            n = _single_count(s.run("MATCH (n) RETURN count(n) AS c").single(), field="node count")
            e = _single_count(s.run("MATCH ()-[r]->() RETURN count(r) AS c").single(), field="edge count")
            labels = _distribution(
                s.run("MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS c ORDER BY c DESC"),
                key="label",
                field="label",
            )
            rels = _distribution(
                s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC"),
                key="t",
                field="relationship type",
            )
            extracted = _single_count(
                s.run("MATCH ()-[r {source:'doc'}]->() RETURN count(r) AS c").single(),
                field="document-extracted edge count",
            )
            return {"nodes": n, "edges": e, "by_label": labels, "by_rel": rels, "doc_extracted": extracted}
    finally:
        drv.close()


def ping():
    try:
        run_read("RETURN 1 AS ok")
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, str(e)
