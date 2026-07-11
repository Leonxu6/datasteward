"""治理化 Action（Ontology 写回）——对标 Palantir Action Type。

一次 Action = 事务式编辑，五要件：Parameters / Submission criteria / Rules / Permissions(独立于读) / Side effects(审计)。
闭环：写回 **PG 源库**（数仓 StarRocks 仍只读）→ Flink CDC 同步回 StarRocks。
每次执行强制：① 写回权限 ② 提交条件 ③ 可选人工审批 ④ 全量审计(actionExecute) ⑤ 可回滚。

Action 清单（Phase 1→3）：
- adjust_safety_stock 调整安全库存阈值（Modify material.safety_stock）
- create_purchase_requisition 生成采购申请（Create purchase_order 行）
- create_delivery 发起发货（Create delivery_note，提交条件=库存≥发货量）

通用回滚：记录 op(update|insert) + 表 + 主键 + before；update→恢复列值，insert→删除该行。
见 docs/palantir/09。
"""
from datetime import date, timedelta
from datetime import datetime

from dm.config import (
    SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD, SRC_PG_PORT, SRC_PG_USER,
)
from dm.security import User, can_execute_action, user_from_env
from dm.warehouse.store import append_log, read_log

TODAY = date(2026, 6, 25)  # 与 warehouse/generate.py 固定日期一致（eval 真值依赖）

ACTION_TYPES = {
    "adjust_safety_stock": {
        "display_name": "调整安全库存阈值", "object_type": "Material",
        "parameters": [
            {"name": "material_id", "type": "String", "required": True, "desc": "物料编码"},
            {"name": "new_value", "type": "Integer", "required": True, "desc": "新安全库存阈值(>=0)"},
        ],
        "submission_criteria": "new_value 为非负整数；物料存在",
        "rule": "Modify object：material.safety_stock ← new_value",
    },
    "create_purchase_requisition": {
        "display_name": "生成采购申请", "object_type": "PurchaseOrder",
        "parameters": [
            {"name": "material_id", "type": "String", "required": True, "desc": "物料编码"},
            {"name": "supplier_id", "type": "String", "required": True, "desc": "供应商编码"},
            {"name": "qty", "type": "Integer", "required": True, "desc": "申请数量(>0)"},
        ],
        "submission_criteria": "qty>0；物料与供应商存在",
        "rule": "Create object：新增 purchase_order 行（状态=未完成）",
    },
    "create_delivery": {
        "display_name": "发起发货", "object_type": "SalesOrder",
        "parameters": [
            {"name": "so_id", "type": "String", "required": True, "desc": "销售单号"},
            {"name": "qty", "type": "Integer", "required": True, "desc": "发货数量(>0)"},
        ],
        "submission_criteria": "qty>0；销售单存在；**现有库存≥发货量**（治理化提交条件）",
        "rule": "Create object：新增 delivery_note 行（状态=已发货）",
    },
}


def list_action_types() -> list:
    return [{"action": k, **v} for k, v in ACTION_TYPES.items()]


def _pg_conn():
    import psycopg
    return psycopg.connect(host=SRC_PG_HOST, port=SRC_PG_PORT, user=SRC_PG_USER,
                           password=SRC_PG_PASSWORD, dbname=SRC_PG_DB, connect_timeout=15)


def _new_id(prefix="ACT"):
    return prefix + datetime.now().strftime("%Y%m%d%H%M%S%f")


def _audit_action(aid, action, params, user: User, decision, detail, table="", ok=True):
    append_log("audit_log", {
        "audit_id": "A" + datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "ts": datetime.now().isoformat(timespec="seconds"),
        "session_id": aid, "channel": "action",
        "category": "actionExecute", "decision": decision,
        "user": user.name, "role": user.role, "purpose": user.purpose,
        "tool_name": action, "tool_args": str(params), "sql": "",
        "tables_touched": table, "markings": "",
        "row_count": 0, "duration_ms": 0, "ok": ok, "error": "" if ok else detail,
    })


def _record(aid, action, params, user: User, *, table, op, pk_col, pk_val,
            before, after, status):
    append_log("action_log", {
        "action_id": aid, "ts": datetime.now().isoformat(timespec="seconds"),
        "action": action, "params": params, "user": user.name, "role": user.role,
        "purpose": user.purpose, "table": table, "op": op, "pk_col": pk_col, "pk_val": pk_val,
        "target": pk_val, "before": before, "after": after, "status": status, "rolled_back": False,
    })


def _validate(action, params) -> str:
    """提交条件（不需 DB 的部分）；返回错误串（None 通过）。"""
    if action == "adjust_safety_stock":
        if not params.get("material_id"):
            return "material_id 必填"
        try:
            if int(params.get("new_value")) < 0:
                return "new_value 不能为负"
        except (TypeError, ValueError):
            return "new_value 必须为整数"
    elif action == "create_purchase_requisition":
        if not params.get("material_id") or not params.get("supplier_id"):
            return "material_id、supplier_id 必填"
        try:
            if int(params.get("qty")) <= 0:
                return "qty 必须为正整数"
        except (TypeError, ValueError):
            return "qty 必须为整数"
    elif action == "create_delivery":
        if not params.get("so_id"):
            return "so_id 必填"
        try:
            if int(params.get("qty")) <= 0:
                return "qty 必须为正整数"
        except (TypeError, ValueError):
            return "qty 必须为整数"
    else:
        return f"未知 Action：{action}"
    return None


def execute_action(action, params, user: User = None, approve: bool = False,
                   action_id: str = None) -> dict:
    """执行（或预览待审批）一次治理化 Action。approve=False 只预览、记 pending、不写库。

    action_id: 审批阶段传入原 pending 的 id 以复用，保证 pending→executed→rolled_back
    是同一个 Action（否则审批会另起新 id，原 pending 成孤儿、按原 id 回滚失败）。"""
    user = user or user_from_env()
    aid = action_id or _new_id()

    ok, reason = can_execute_action(user, action)   # ① 写回权限（独立于读）
    if not ok:
        _audit_action(aid, action, params, user, "deny", reason, ok=False)
        return {"ok": False, "action_id": aid, "error": "权限不足：" + reason}

    err = _validate(action, params)                 # ② 提交条件（无需 DB）
    if err:
        _audit_action(aid, action, params, user, "reject", err, ok=False)
        return {"ok": False, "action_id": aid, "error": "提交条件不满足：" + err}

    con = _pg_conn()
    try:
        with con.cursor() as cur:
            handler = _HANDLERS[action]
            return handler(cur, con, aid, action, params, user, approve)
    finally:
        con.close()


# ---------- 各 Action 处理器（cur 在事务中；approve=False 时 rollback 不写） ----------
def _h_adjust_safety_stock(cur, con, aid, action, params, user, approve):
    mid, nv = params["material_id"], int(params["new_value"])
    cur.execute("SELECT safety_stock FROM material WHERE material_id=%s", (mid,))
    row = cur.fetchone()
    if not row:
        con.rollback()
        _audit_action(aid, action, params, user, "reject", f"物料 {mid} 不存在", "material", ok=False)
        return {"ok": False, "action_id": aid, "error": f"物料 {mid} 不存在"}
    old = row[0]
    if not approve:
        con.rollback()
        _record(aid, action, params, user, table="material", op="update", pk_col="material_id",
                pk_val=mid, before={"safety_stock": old}, after={"safety_stock": nv}, status="pending")
        _audit_action(aid, action, params, user, "pending", f"待审批 {mid}:{old}->{nv}", "material")
        return {"ok": False, "action_id": aid, "status": "pending_approval",
                "preview": {"material_id": mid, "old": old, "new": nv},
                "message": f"需审批：material {mid} safety_stock {old}→{nv}"}
    cur.execute("UPDATE material SET safety_stock=%s WHERE material_id=%s", (nv, mid))
    con.commit()
    _record(aid, action, params, user, table="material", op="update", pk_col="material_id",
            pk_val=mid, before={"safety_stock": old}, after={"safety_stock": nv}, status="executed")
    _audit_action(aid, action, params, user, "allow", f"{mid}:{old}->{nv}", "material")
    return {"ok": True, "action_id": aid, "target": mid, "old": old, "new": nv,
            "message": f"已写回 PG：material {mid} safety_stock {old}→{nv}（CDC 将同步）"}


def _h_create_purchase_requisition(cur, con, aid, action, params, user, approve):
    mid, sid, qty = params["material_id"], params["supplier_id"], int(params["qty"])
    cur.execute("SELECT 1 FROM material WHERE material_id=%s", (mid,))
    if not cur.fetchone():
        con.rollback()
        _audit_action(aid, action, params, user, "reject", f"物料 {mid} 不存在", "purchase_order", ok=False)
        return {"ok": False, "action_id": aid, "error": f"物料 {mid} 不存在"}
    cur.execute("SELECT 1 FROM supplier WHERE supplier_id=%s", (sid,))
    if not cur.fetchone():
        con.rollback()
        _audit_action(aid, action, params, user, "reject", f"供应商 {sid} 不存在", "purchase_order", ok=False)
        return {"ok": False, "action_id": aid, "error": f"供应商 {sid} 不存在"}
    po_id = params.get("_po_id") or _new_id("PR")
    params["_po_id"] = po_id   # 存入 params，保证 pending→approve 复用同一 ID（否则两步各生成不同 ID）
    exp = (TODAY + timedelta(days=14)).isoformat()
    preview = {"po_id": po_id, "material_id": mid, "supplier_id": sid, "qty": qty,
               "order_date": TODAY.isoformat(), "expected_date": exp, "status": "未完成"}
    if not approve:
        con.rollback()
        _record(aid, action, params, user, table="purchase_order", op="insert", pk_col="po_id",
                pk_val=po_id, before=None, after=preview, status="pending")
        _audit_action(aid, action, params, user, "pending", f"待审批 采购申请 {po_id}", "purchase_order")
        return {"ok": False, "action_id": aid, "status": "pending_approval", "preview": preview,
                "message": f"需审批：生成采购申请 {po_id}（{mid}×{qty} 供应商 {sid}）"}
    cur.execute(
        "INSERT INTO purchase_order (po_id,line_no,supplier_id,material_id,qty,unit_price,"
        "order_date,expected_date,status) VALUES (%s,1,%s,%s,%s,0,%s,%s,'未完成')",
        (po_id, sid, mid, qty, TODAY.isoformat(), exp))
    con.commit()
    _record(aid, action, params, user, table="purchase_order", op="insert", pk_col="po_id",
            pk_val=po_id, before=None, after=preview, status="executed")
    _audit_action(aid, action, params, user, "allow", f"创建采购申请 {po_id}", "purchase_order")
    return {"ok": True, "action_id": aid, "target": po_id, "created": preview,
            "message": f"已生成采购申请 {po_id}：{mid}×{qty}（供应商 {sid}，写回 PG，CDC 将同步）"}


def _h_create_delivery(cur, con, aid, action, params, user, approve):
    so_id, qty = params["so_id"], int(params["qty"])
    cur.execute("SELECT customer_id, material_id FROM sales_order WHERE so_id=%s LIMIT 1", (so_id,))
    so = cur.fetchone()
    if not so:
        con.rollback()
        _audit_action(aid, action, params, user, "reject", f"销售单 {so_id} 不存在", "delivery_note", ok=False)
        return {"ok": False, "action_id": aid, "error": f"销售单 {so_id} 不存在"}
    cust, mid = so
    # 治理化提交条件：现有库存 ≥ 发货量（Palantir submission criteria）
    cur.execute("SELECT COALESCE(SUM(qty),0) FROM inventory WHERE material_id=%s", (mid,))
    stock = cur.fetchone()[0]
    if stock < qty:
        con.rollback()
        _audit_action(aid, action, params, user, "reject",
                      f"库存不足：{mid} 现有 {stock} < 发货 {qty}", "delivery_note", ok=False)
        return {"ok": False, "action_id": aid,
                "error": f"提交条件不满足：物料 {mid} 现有库存 {stock} < 发货量 {qty}，不可发货"}
    did = params.get("_delivery_id") or _new_id("DN")
    params["_delivery_id"] = did   # pending→approve 复用同一 ID
    preview = {"delivery_id": did, "so_id": so_id, "customer_id": cust, "material_id": mid,
               "qty": qty, "delivery_date": TODAY.isoformat(), "status": "已发货"}
    if not approve:
        con.rollback()
        _record(aid, action, params, user, table="delivery_note", op="insert", pk_col="delivery_id",
                pk_val=did, before=None, after=preview, status="pending")
        _audit_action(aid, action, params, user, "pending", f"待审批 发货 {did}", "delivery_note")
        return {"ok": False, "action_id": aid, "status": "pending_approval", "preview": preview,
                "message": f"需审批：发货 {did}（{so_id} 物料 {mid}×{qty}，库存 {stock} 充足）"}
    cur.execute(
        "INSERT INTO delivery_note (delivery_id,so_id,customer_id,material_id,qty,delivery_date,status)"
        " VALUES (%s,%s,%s,%s,%s,%s,'已发货')",
        (did, so_id, cust, mid, qty, TODAY.isoformat()))
    con.commit()
    _record(aid, action, params, user, table="delivery_note", op="insert", pk_col="delivery_id",
            pk_val=did, before=None, after=preview, status="executed")
    _audit_action(aid, action, params, user, "allow", f"发货 {did}", "delivery_note")
    return {"ok": True, "action_id": aid, "target": did, "created": preview,
            "message": f"已发货 {did}：{so_id} {mid}×{qty}（库存 {stock} 充足，写回 PG，CDC 将同步）"}


_HANDLERS = {
    "adjust_safety_stock": _h_adjust_safety_stock,
    "create_purchase_requisition": _h_create_purchase_requisition,
    "create_delivery": _h_create_delivery,
}


def approve_action(action_id, user: User = None) -> dict:
    """批准一个 pending Action → 实际写回。"""
    user = user or user_from_env()
    rec = next((r for r in read_log("action_log") if r["action_id"] == action_id), None)
    if not rec:
        return {"ok": False, "error": "未找到该 Action"}
    if rec["status"] != "pending":
        return {"ok": False, "error": f"该 Action 状态为 {rec['status']}，不可审批"}
    return execute_action(rec["action"], rec["params"], user=user, approve=True,
                          action_id=action_id)


def rollback_action(action_id, user: User = None) -> dict:
    """回滚一个已执行 Action（通用：update→恢复列值，insert→删除该行）。"""
    user = user or user_from_env()
    recs = [r for r in read_log("action_log") if r["action_id"] == action_id]
    rec = recs[-1] if recs else None
    if not rec or rec["status"] != "executed":
        return {"ok": False, "error": "未找到可回滚的已执行 Action"}
    if rec.get("rolled_back"):
        return {"ok": False, "error": "该 Action 已回滚过"}
    ok, reason = can_execute_action(user, rec["action"])
    if not ok:
        return {"ok": False, "error": "权限不足：" + reason}
    con = _pg_conn()
    try:
        with con.cursor() as cur:
            if rec["op"] == "update":
                sets = ", ".join(f"{k}=%s" for k in rec["before"])
                cur.execute(f"UPDATE {rec['table']} SET {sets} WHERE {rec['pk_col']}=%s",
                            (*rec["before"].values(), rec["pk_val"]))
                detail = f"恢复 {rec['table']}.{rec['pk_val']} → {rec['before']}"
            else:  # insert → 删除
                cur.execute(f"DELETE FROM {rec['table']} WHERE {rec['pk_col']}=%s", (rec["pk_val"],))
                detail = f"删除 {rec['table']}.{rec['pk_val']}"
        con.commit()
    finally:
        con.close()
    append_log("action_log", {**rec, "status": "rolled_back", "rolled_back": True,
                              "rollback_ts": datetime.now().isoformat(timespec="seconds")})
    _audit_action("RB" + action_id, rec["action"], {"rollback_of": action_id}, user, "allow",
                  detail, rec["table"])
    return {"ok": True, "message": f"已回滚：{detail}"}


def pending_actions() -> list:
    seen = {}
    for r in read_log("action_log"):
        seen[r["action_id"]] = r
    return [r for r in seen.values() if r["status"] == "pending"]


def action_history() -> list:
    seen = {}
    for r in read_log("action_log"):
        seen[r["action_id"]] = r
    return list(seen.values())
