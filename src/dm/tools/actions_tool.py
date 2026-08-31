"""治理化写回工具（治理内核版）：execute_action。

写路径唯一入口：权限（独立于读权）→ 参数验证 → 默认 pending 待人工审批 → 全审计 → 可回滚。
pending 语义非阻塞：立即返回预览与参考号，人工在管理平台审批台批准后才真正写 PG 源库。
"""
import json
import time

from dm.tools.audit import audit_event
from dm.tools.principal import Principal


def execute_action(principal: Principal, action: str, material_id: str = "", new_value: int = 0,
                   supplier_id: str = "", qty: int = 0, so_id: str = "",
                   approve: bool = False) -> str:
    """执行一次治理化写回 Action（adjust_safety_stock / create_purchase_requisition / create_delivery）。"""
    if not isinstance(approve, bool):
        return "ERROR: approve 必须是布尔值"
    t0 = time.time()
    from dm.ontology.actions import execute_action as _exec
    params = {"material_id": material_id, "new_value": new_value, "supplier_id": supplier_id,
              "qty": qty, "so_id": so_id}
    try:
        res = _exec(action, params, user=principal.to_user(), approve=approve)
        audit_event(principal, "execute_action", {"action": action, **params, "approve": approve}, "",
                    [res.get("target", "")], 1 if res.get("ok") else 0, t0, res.get("ok", False),
                    error="" if res.get("ok") else res.get("error", ""),
                    category="actionExecute", decision=("allow" if res.get("ok") else "deny"))
        return json.dumps(res, ensure_ascii=False, default=str, indent=2)
    except Exception as e:  # noqa: BLE001
        audit_event(principal, "execute_action", {"action": action}, "", [], 0, t0, False, str(e),
                    category="actionExecute", decision="error")
        return f"ERROR: Action 执行失败: {e}"
