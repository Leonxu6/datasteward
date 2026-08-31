"""治理化写回工具（治理内核版）：execute_action。

写路径唯一入口：权限（独立于读权）→ 参数验证 → 默认 pending 待人工审批 → 全审计 → 可回滚。
pending 语义非阻塞：立即返回预览与参考号，人工在管理平台审批台批准后才真正写 PG 源库。
"""
import json
import time

from dm.tools.audit import audit_event
from dm.tools.principal import Principal


def _validated_result(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("action executor returned a malformed result")
    ok = value.get("ok")
    if not isinstance(ok, bool):
        raise ValueError("action executor result must include boolean ok")
    target = value.get("target", "")
    if not isinstance(target, str):
        raise ValueError("action executor target must be text")
    error = value.get("error", "")
    if not isinstance(error, str):
        raise ValueError("action executor error must be text")
    return value


def _error_category(exc: BaseException) -> str:
    name = type(exc).__name__
    return name if name and len(name) <= 100 else "ActionExecutionError"


def _audit_failure(principal: Principal, action: str, t0: float, exc: BaseException) -> None:
    try:
        audit_event(
            principal, "execute_action", {"action": action}, "", [], 0, t0, False,
            _error_category(exc), category="actionExecute", decision="error",
        )
    except Exception:  # noqa: BLE001
        return


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
        res = _validated_result(_exec(action, params, user=principal.to_user(), approve=approve))
    except Exception as exc:  # noqa: BLE001
        _audit_failure(principal, action, t0, exc)
        return "ERROR: Action 执行失败"

    try:
        audit_event(principal, "execute_action", {"action": action, **params, "approve": approve}, "",
                    [res.get("target", "")], 1 if res["ok"] else 0, t0, res["ok"],
                    error="" if res["ok"] else res.get("error", ""),
                    category="actionExecute", decision=("allow" if res["ok"] else "deny"))
    except Exception:  # noqa: BLE001
        res = dict(res)
        res["audit_ok"] = False
        res["audit_warning"] = "action completed but audit persistence failed"

    return json.dumps(res, ensure_ascii=False, default=str, indent=2)
