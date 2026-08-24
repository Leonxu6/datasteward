"""OSDK-lite：本体的**只读**访问 API（对标 Palantir OSDK 的 objects.X.get/where/iterate）。

对象数据来自 StarRocks（`connect_ro`）。返回以 **property api_name** 为键（对象语义），
而非原始列名——消费方（智能体 / Object Explorer）按对象说话，不碰表结构。

权限与审计：Phase 1 治理切片会在此之上包一层策略（行/列过滤 + JSONL 审计）；
本模块只负责"取对象/取链接"，保持单一职责。
"""
from typing import Optional

from dm.ontology.model import ObjectType, get_object_type, incoming_links
from dm.warehouse.store import connect_ro


def _positive_limit(value: object, *, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{field} must be between 1 and {maximum}")
    return value


def _row_to_obj(ot: ObjectType, row: tuple, cols: list) -> dict:
    """一行 → 以 property api_name 为键的对象 dict。"""
    raw = dict(zip(cols, row))
    return {p.api_name: raw.get(p.column) for p in ot.properties}


def _mask_obj(ot: ObjectType, obj: dict, um: set) -> dict:
    """按有效 Marking `um` 把对象里受限属性（列级/属性安全策略）屏蔽为 None（单元格级）。"""
    from dm.security.model import column_markings
    out = dict(obj)
    for p in ot.properties:
        marks = column_markings(ot.table, p.column)
        if marks and not set(marks) <= um:
            out[p.api_name] = None
    return out


def list_objects(api_name: str, limit: int = 50, order_by: Optional[str] = None, user=None) -> dict:
    """列出某对象类型的实例（≈ OSDK objects.X.page/iterate）。
    传入 user 时按对象层强制权限：表级 Marking 可见性 + 行级对象策略(WHERE) + 列级属性策略(屏蔽)。"""
    limit = _positive_limit(limit, field="limit", maximum=500)
    ot = get_object_type(api_name)
    if not ot:
        return {"error": f"未知对象类型 {api_name}"}
    um = None
    where = ""
    if user is not None:
        from dm.security import can_read_table, effective_user_markings, row_filter
        if not can_read_table(user, ot.table):
            return {"object_type": ot.api_name, "display_name": ot.display_name,
                    "count": 0, "objects": [], "error": f"角色 {user.role} 无权访问该对象类型（缺 Marking）"}
        um = effective_user_markings(user)
        rf = row_filter(user, ot.table)
        if rf:
            where = f" WHERE `{rf[0]}`='" + str(rf[1]).replace("'", "''") + "'"
    sql = f"SELECT * FROM `{ot.table}`" + where
    if order_by and ot.prop(order_by):
        sql += f" ORDER BY `{ot.prop(order_by).column}`"
    sql += f" LIMIT {limit}"
    con = connect_ro()
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()
    objs = [_row_to_obj(ot, r, cols) for r in rows]
    if um is not None:
        objs = [_mask_obj(ot, o, um) for o in objs]
    return {"object_type": ot.api_name, "display_name": ot.display_name,
            "count": len(rows), "objects": objs, "row_policy": bool(where)}


def _fetch_row(ot: ObjectType, pk_value) -> Optional[dict]:
    pk = ot.primary_key[0]
    con = connect_ro()
    try:
        cur = con.execute(f"SELECT * FROM `{ot.table}` WHERE `{pk}` = %s LIMIT 1", (pk_value,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
    finally:
        con.close()
    if not row:
        return None
    return dict(zip(cols, row))


def get_object(api_name: str, pk_value, user=None) -> dict:
    """按主键取单个对象（≈ OSDK objects.X.get(pk)）。传入 user 则做表级可见性 + 列级属性屏蔽。"""
    ot = get_object_type(api_name)
    if not ot:
        return {"error": f"未知对象类型 {api_name}"}
    if user is not None:
        from dm.security import can_read_table
        if not can_read_table(user, ot.table):
            return {"error": f"角色 {user.role} 无权访问该对象类型（缺 Marking）"}
    raw = _fetch_row(ot, pk_value)
    if raw is None:
        return {"error": f"{ot.api_name}({pk_value}) 不存在"}
    obj = {p.api_name: raw.get(p.column) for p in ot.properties}
    if user is not None:
        from dm.security import effective_user_markings
        obj = _mask_obj(ot, obj, effective_user_markings(user))
    return {"object_type": ot.api_name, "primary_key": ot.primary_key[0], "object": obj}


def get_links(api_name: str, pk_value, per_link_limit: int = 20) -> dict:
    """取某对象一跳可达的相关对象（≈ Palantir Search-Around）。

    - outgoing：本对象的外键 → 父对象（如 采购单 → 供应商）
    - incoming：引用本对象的子对象（如 供应商 ← 各采购单）
    多跳/跨域走知识图谱（Neo4j graph_query）；本处只做一跳的对象化遍历。
    """
    per_link_limit = _positive_limit(per_link_limit, field="per_link_limit", maximum=200)
    ot = get_object_type(api_name)
    if not ot:
        return {"error": f"未知对象类型 {api_name}"}
    raw = _fetch_row(ot, pk_value)
    if raw is None:
        return {"error": f"{ot.api_name}({pk_value}) 不存在"}

    outgoing = {}
    for lk in ot.links:
        fk_val = raw.get(lk.from_property)
        if fk_val is None:
            continue
        parent = get_object(lk.to_object, fk_val)
        if "object" in parent:
            outgoing[lk.api_name] = {"to": lk.to_object, "display": lk.display_name,
                                     "object": parent["object"]}

    incoming = {}
    con = connect_ro()
    try:
        for lk in incoming_links(ot.api_name):
            child = get_object_type(lk.from_object)
            cur = con.execute(
                f"SELECT * FROM `{child.table}` WHERE `{lk.from_property}` = %s LIMIT {per_link_limit}",
                (pk_value,))
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            if rows:
                # 键须唯一：多个子表的外键可能派生成同名关系（如都叫 material），
                # 用 "子对象.关系" 作键避免互相覆盖。
                incoming[f"{lk.from_object}.{lk.api_name}"] = {
                    "from": lk.from_object, "display": lk.display_name,
                    "count": len(rows),
                    "objects": [_row_to_obj(child, r, cols) for r in rows]}
    finally:
        con.close()

    return {"object_type": ot.api_name, "primary_key": pk_value,
            "outgoing": outgoing, "incoming": incoming}
