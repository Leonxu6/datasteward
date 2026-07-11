"""构建知识图谱（S3）。

骨架（skeleton）：从 StarRocks 按 schema 把**供应链核心表**的业务行→节点、外键→语义边，得到忠实的关系图。
增强（extract）：LLM（经网关，本地模型）读文档，抽出 ERP 里没有的关系（物料↔设备、供应商↔合同、到货↔质检），
                 对齐到真实实体 ID 后并入图——这正是 KG 相对纯结构化的增量价值。

CLI: dm-kg build|skeleton|extract|status|clear
"""
import json
import sys

from dm.schema import TABLES, table_by_name
from dm.warehouse.store import connect_ro

# 供应链核心子集（聚焦可查询的跨域子图；HR/单位/字典等噪声表不入图）
KG_TABLES = ["material_category", "material", "supplier", "customer", "warehouse",
             "storage_location", "inventory", "purchase_order", "purchase_arrival",
             "sales_order", "delivery_note", "production_order", "production_material_req"]
_KGSET = set(KG_TABLES)

# 外键列 → 语义关系名（可读、便于多跳查询）；缺省回退 REF_<col>
EDGE_NAME = {
    "category_id": "IN_CATEGORY", "parent_id": "CHILD_OF",
    "material_id": "OF_MATERIAL", "warehouse_id": "IN_WAREHOUSE", "location_id": "AT_LOCATION",
    "supplier_id": "FROM_SUPPLIER", "customer_id": "FOR_CUSTOMER",
    "po_id": "OF_PO", "so_id": "OF_SO", "mo_id": "OF_MO",
}


def _label(table):
    return "".join(w.capitalize() for w in table.split("_"))


def _pk_cols(t):
    return t["pk"].split("+")


def _norm(v):
    return None if v is None else str(v)


def skeleton(verbose=True):
    """从 StarRocks 重建骨架：业务行→节点、FK→语义边。清空后重建（幂等）。"""
    from dm.kg.store import driver
    drv = driver()
    sr = connect_ro()
    n_nodes = n_edges = 0
    try:
        with drv.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
            for name in KG_TABLES:
                lab = _label(name)
                s.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{lab}) ON (n.id)")
                s.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{lab}) ON (n.{_pk_cols(table_by_name(name))[0]})")

            cache = {}  # name -> list[dict] 行（建边时复用）
            for name in KG_TABLES:
                t = table_by_name(name)
                lab = _label(name)
                cur = sr.execute(f'SELECT * FROM `{name}`')
                cols = [d[0] for d in cur.description]
                rows = [{cols[i]: _norm(r[i]) for i in range(len(cols))} for r in cur.fetchall()]
                pkc = _pk_cols(t)
                for d in rows:
                    d["id"] = "#".join(str(d.get(c)) for c in pkc)
                    d["_cn"] = t["cn"]
                cache[name] = rows
                s.run(f"UNWIND $recs AS rec CREATE (n:{lab}) SET n = rec", recs=rows)
                n_nodes += len(rows)
                if verbose:
                    print(f"  节点 {lab:24} {len(rows):>5}")

            for name in KG_TABLES:
                t = table_by_name(name)
                lab = _label(name)
                for (col, ref) in t["fks"]:
                    if ref not in _KGSET:
                        continue
                    ref_pk0 = _pk_cols(table_by_name(ref))[0]
                    ename = EDGE_NAME.get(col, f"REF_{col.upper()}")
                    rlab = _label(ref)
                    edges = [{"src": d["id"], "dst": d[col]} for d in cache[name] if d.get(col) is not None]
                    if not edges:
                        continue
                    s.run(f"UNWIND $edges AS e MATCH (a:{lab} {{id:e.src}}),(b:{rlab}) "
                          f"WHERE b.{ref_pk0}=e.dst CREATE (a)-[:{ename} {{source:'fk'}}]->(b)", edges=edges)
                    n_edges += len(edges)
                    if verbose:
                        print(f"  边  {lab}-[{ename}]->{rlab}: {len(edges)}")
    finally:
        sr.close()
        drv.close()
    print(f"=== 骨架完成：{n_nodes} 节点 / {n_edges} 边（FK）===")
    return n_nodes, n_edges


# ----------------------------- 文档关系抽取（LLM 经网关） -----------------------------
_EXTRACT_PROMPT = """你是知识图谱关系抽取器。下面是一篇制造业内部文档。请抽出文档中体现的、\
**结构化 ERP 里通常没有的**实体间关系（如：物料↔加工设备、供应商↔采购合同、到货批次↔质检结论、物料↔技术规格/SOP）。
只输出 JSON，格式：{"triples":[{"s":"<头实体ID>","s_type":"<Material|Supplier|Customer|Equipment|Document|Arrival|...>",\
"r":"<关系，大写下划线，如 PROCESSED_ON / HAS_CONTRACT / INSPECTED_AS / HAS_SPEC>",\
"o":"<尾实体ID>","o_type":"<...>","note":"<一句话依据>"}]}
实体 ID 用文档里出现的真实编号（物料 M####、供应商 S###、到货 PA####、设备如 CNC-08、文档本身用其 doc_id）。
不要编造文档中没有的关系。只回 JSON，不要解释。"""


def _llm_extract(doc_id, title, body):
    prompt = f"{_EXTRACT_PROMPT}\n\n[doc_id={doc_id}] {title}\n{body}"
    from dm.llm import chat
    try:
        out = chat([{"role": "user", "content": prompt}], temperature=0.0, timeout=120).strip()
    except RuntimeError:
        return []
    i, j = out.find("{"), out.rfind("}")
    if i < 0 or j < 0:
        return []
    try:
        return json.loads(out[i:j + 1]).get("triples", [])
    except Exception:  # noqa: BLE001
        return []


def extract(verbose=True):
    """读 document 表的每篇文档 → LLM 抽关系 → 并入图（Equipment/Document 节点 + 抽取边，标 source='doc'）。"""
    import psycopg2

    from dm.config import SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD, SRC_PG_PORT, SRC_PG_USER
    from dm.kg.store import driver
    pg = psycopg2.connect(host=SRC_PG_HOST, port=SRC_PG_PORT, user=SRC_PG_USER,
                          password=SRC_PG_PASSWORD, dbname=SRC_PG_DB, connect_timeout=10)
    cur = pg.cursor()
    cur.execute("SELECT doc_id, title, source_path, entities FROM document ORDER BY doc_id")
    docs = cur.fetchall()
    drv = driver()
    n_doc = n_tri = 0
    try:
        with drv.session() as s:
            # 清掉上一轮抽取的边/文档节点（只动 source='doc' 的，骨架不碰）
            s.run("MATCH ()-[r {source:'doc'}]->() DELETE r")
            s.run("MATCH (n:Document) DETACH DELETE n")
            s.run("MATCH (n:Equipment) DETACH DELETE n")
            for doc_id, title, path, entities in docs:
                from pathlib import Path
                body = Path(path).read_text(encoding="utf-8") if path and Path(path).exists() else (title or "")
                triples = _llm_extract(doc_id, title, body[:3000])
                # 文档节点
                s.run("MERGE (d:Document {id:$id}) SET d.title=$t, d.entities=$e, d._cn='文档'",
                      id=doc_id, t=title, e=entities or "")
                for tr in triples:
                    sid, st_, r, oid, ot = (str(tr.get("s", "")).strip(), tr.get("s_type", ""),
                                            tr.get("r", "REL"), str(tr.get("o", "")).strip(), tr.get("o_type", ""))
                    if not sid or not oid or not r:
                        continue
                    r = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in r.upper())[:40] or "REL"
                    note = str(tr.get("note", ""))[:200]
                    # 头/尾节点：已存在(骨架)的按 pk0 匹配；否则按类型 MERGE（Equipment/Document 等新类）
                    s.run(
                        "MERGE (a {id:$sid}) ON CREATE SET a:%s, a._cn=$st "
                        "MERGE (b {id:$oid}) ON CREATE SET b:%s, b._cn=$ot "
                        "MERGE (a)-[rel:%s {source:'doc'}]->(b) SET rel.note=$note, rel.doc=$doc"
                        % (_safe_label(st_), _safe_label(ot), r),
                        sid=sid, oid=oid, st=st_, ot=ot, note=note, doc=doc_id)
                    n_tri += 1
                n_doc += 1
                if verbose:
                    print(f"  抽取 {doc_id} «{(title or '')[:22]}» → {len(triples)} 关系")
    finally:
        pg.close()
        drv.close()
    print(f"=== 文档抽取完成：{n_doc} 篇 / {n_tri} 关系（source='doc'）===")
    return n_doc, n_tri


def _safe_label(s):
    s = "".join(ch for ch in str(s or "") if ch.isalnum())
    return s[:1].upper() + s[1:] if s else "Entity"


def status():
    from dm.kg.store import counts, ping
    ok, err = ping()
    if not ok:
        print(f"Neo4j 不可达：{err}")
        return
    c = counts()
    print(f"=== 知识图谱：{c['nodes']} 节点 / {c['edges']} 边（其中文档抽取 {c['doc_extracted']}）===")
    print("  标签:", ", ".join(f"{k}={v}" for k, v in list(c["by_label"].items())[:12]))
    print("  关系:", ", ".join(f"{k}={v}" for k, v in list(c["by_rel"].items())[:12]))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        skeleton()
        extract()
        status()
    elif cmd == "skeleton":
        skeleton()
    elif cmd == "extract":
        extract()
    elif cmd == "status":
        status()
    elif cmd == "clear":
        from dm.kg.store import run_write
        run_write("MATCH (n) DETACH DELETE n")
        print("已清空图。")
    else:
        print(f"未知命令 {cmd}。可用：build / skeleton / extract / status / clear")


if __name__ == "__main__":
    main()
