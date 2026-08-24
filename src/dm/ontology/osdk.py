"""OSDK-lite：本体的**只读**访问 API（对标 Palantir OSDK 的 objects.X.get/where/iterate）。"""
from typing import Optional

from dm.ontology.model import ObjectType, get_object_type, incoming_links
from dm.warehouse.store import connect_ro


def _positive_limit(value: object, *, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{field} must be between 1 and {maximum}")
    return value


def _order_property(ot: ObjectType, order_by: object):
    if order_by is None:
        return None
    if not isinstance(order_by, str) or not order_by or order_by != order_by.strip():
        raise ValueError("order_by must be clean non-empty text")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in order_by):
        raise ValueError("order_by contains control characters")
    prop = ot.prop(order_by)
    if prop is None:
        raise ValueError(f"unknown order_by property: {order_by}")
    return prop


def _row_to_raw(row, cols: list) -> dict:
    try:
        width = len(row)
    except TypeError as exc:
        raise ValueError("object query rows must be sized sequences") from exc
    if width != len(cols):
        raise ValueError("object query row length does not match cursor columns")
    if any(not isinstance(col, str) or not col for col in cols):
        raise ValueError("object query columns must be non-empty strings")
    if len(set(cols)) != len(cols):
        raise ValueError("object query returned duplicate column names")
    return dict(zip(cols, row))


def _row_to_obj(ot: ObjectType, row: tuple, cols: list) -> dict:
    raw = _row_to_raw(row, cols)
    return {p.api_name: raw.get(p.column) for p in ot.properties}


def _mask_obj(ot: ObjectType, obj: dict, um: set) -> dict:
    from dm.security.model import column_markings
    out = dict(obj)
    for p in ot.properties:
        marks = column_markings(ot.table, p.column)
        if marks and not set(marks) <= um:
            out[p.api_name] = None
    return out


def list_objects(api_name: str, limit: int = 50, order_by: Optional[str] = None, user=None) -> dict:
    limit = _positive_limit(limit, field="limit", maximum=500)
    ot = get_object_type(api_name)
    if not ot:
        return {"error": f"未知对象类型 {api_name}"}
    order_prop = _order_property(ot, order_by)
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
    if order_prop is not None:
        sql += f" ORDER BY `{order_prop.column}`"
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
    if row is None:
        return None
    return _row_to_raw(row, cols)


def get_object(api_name: str, pk_value, user=None) -> dict:
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
                incoming[f"{lk.from_object}.{lk.api_name}"] = {
                    "from": lk.from_object, "display": lk.display_name,
                    "count": len(rows),
                    "objects": [_row_to_obj(child, r, cols) for r in rows]}
    finally:
        con.close()

    return {"object_type": ot.api_name, "primary_key": pk_value,
            "outgoing": outgoing, "incoming": incoming}
