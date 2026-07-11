"""数据血缘（Lineage）——从数据集/transform/源注册表自动生成端到端血缘图。

对标 Palantir：血缘是**构建的副产品**（transform 声明 inputs/outputs 即登记依赖），
三大用途——影响分析（正向）、调试溯源（反向）、合规（provenance）。

关键不变量：**安全随血缘传播**（security travels with the data）——
给上游（源/raw 数据集）打的 Marking 会沿血缘自动累加到所有下游数据集（`effective_markings`）。
这与 Palantir "marking 沿数据依赖继承"一致；权限层（security/）据此在查询时施加行列过滤。

节点：source / dataset(raw|refined) / transform；边：源→raw(sync)、raw→transform(input)、transform→refined(output)。
列级血缘（v0）：沿 transform.column_map 反向追溯到 raw 列与源。
"""
from dm.connect.catalog import SOURCES
from dm.datasets.model import DATASETS, TRANSFORMS


def _build_graph():
    nodes: dict = {}
    edges: list = []  # (from_id, to_id, kind)
    for s in SOURCES.values():
        nodes[f"source:{s.name}"] = {"id": f"source:{s.name}", "type": "source", "label": s.name}
    for d in DATASETS.values():
        nid = f"dataset:{d.name}"
        nodes[nid] = {"id": nid, "type": "dataset", "tier": d.tier, "label": d.name}
        if d.source and f"source:{d.source}" in nodes:
            edges.append((f"source:{d.source}", nid, "sync"))
    for t in TRANSFORMS.values():
        tid = f"transform:{t.name}"
        nodes[tid] = {"id": tid, "type": "transform", "kind": t.kind, "label": t.name}
        for inp in t.inputs:
            if f"dataset:{inp}" in nodes:
                edges.append((f"dataset:{inp}", tid, "input"))
        for out in t.outputs:
            if f"dataset:{out}" in nodes:
                edges.append((tid, f"dataset:{out}", "output"))
    return nodes, edges


_NODES, _EDGES = _build_graph()


def lineage_graph() -> dict:
    """全量血缘图（供治理台血缘页渲染）。"""
    return {"nodes": list(_NODES.values()),
            "edges": [{"from": a, "to": b, "kind": k} for a, b, k in _EDGES]}


def _walk(start_id: str, upstream: bool) -> list:
    """沿边 BFS 收集上游（upstream=True）或下游节点 id。"""
    seen, stack = set(), [start_id]
    while stack:
        n = stack.pop()
        for a, b, _ in _EDGES:
            nxt = a if (upstream and b == n) else (b if (not upstream and a == n) else None)
            if nxt and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return [_NODES[i] for i in seen if i in _NODES]


def ancestry(dataset_name: str) -> list:
    """某数据集的上游（它从哪来）——调试/溯源。"""
    return _walk(f"dataset:{dataset_name}", upstream=True)


def impact(dataset_name: str) -> list:
    """某数据集的下游（改它会牵连谁）——影响分析。"""
    return _walk(f"dataset:{dataset_name}", upstream=False)


def column_lineage(dataset_name: str, column: str) -> list:
    """列级血缘：沿 transform.column_map 反向追溯该列的来源链。"""
    chain = [{"dataset": dataset_name, "column": column}]
    cur_ds, cur_col = dataset_name, column
    seen = set()
    while True:
        key = (cur_ds, cur_col)
        if key in seen:
            break
        seen.add(key)
        producer = next((t for t in TRANSFORMS.values() if cur_ds in t.outputs), None)
        if not producer:
            ds = DATASETS.get(cur_ds)
            if ds and ds.source:
                chain.append({"source": ds.source, "column": cur_col})
            break
        src_cols = producer.column_map.get(cur_col, [])
        if not src_cols:
            break
        cur_col = src_cols[0]
        cur_ds = producer.inputs[0] if producer.inputs else None
        if not cur_ds:
            break
        chain.append({"dataset": cur_ds, "column": cur_col, "via": producer.name})
    return chain


def _live_markings(node_id: str) -> list:
    kind, _, name = node_id.partition(":")
    if kind == "source":
        s = SOURCES.get(name)
        return list(s.markings) if s else []
    if kind == "dataset":
        d = DATASETS.get(name)
        return list(d.markings) if d else []
    return []


def effective_markings(dataset_name: str) -> list:
    """某数据集的**有效 Marking** = 自身 + 全部上游（源/数据集）Marking 的并集。
    这就是"安全随血缘传播"：给源/上游打标，下游自动继承。权限层据此做行列过滤。"""
    nid = f"dataset:{dataset_name}"
    ids = set(n["id"] for n in _walk(nid, upstream=True)) | {nid}
    marks = set()
    for i in ids:
        marks.update(_live_markings(i))
    return sorted(marks)
