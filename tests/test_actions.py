"""治理化 Action 审批链回归测试。

回归点：approve_action 必须把原 pending 的 action_id 传给 execute_action 复用，
否则审批会另起新 id → 原 pending 记录成孤儿（审批台永远显示"待审批"）、且按原 id
回滚会找不到"已执行"记录而失败。见 dm/ontology/actions.py。
"""

import pytest

pytestmark = pytest.mark.stack  # 需要可达的 StarRocks/Postgres 栈；不可达自动跳过
from dm.ontology import actions as A
from dm.security import User


def test_approve_reuses_original_action_id(monkeypatch):
    """审批时应复用原 action_id（修复前传下去的是 None → execute_action 会另生成新 id）。"""
    pending = {
        "action_id": "ACT-REGRESSION-1", "status": "pending",
        "action": "adjust_safety_stock",
        "params": {"material_id": "M0001", "new_value": 30},
    }
    monkeypatch.setattr(A, "read_log",
                        lambda name: [pending] if name == "action_log" else [])

    captured = {}

    def fake_execute(action, params, user=None, approve=False, action_id=None):
        captured["action_id"] = action_id
        captured["approve"] = approve
        return {"ok": True, "action_id": action_id}

    monkeypatch.setattr(A, "execute_action", fake_execute)

    A.approve_action("ACT-REGRESSION-1", user=User("审批人", "管理层"))

    assert captured["approve"] is True
    assert captured["action_id"] == "ACT-REGRESSION-1", (
        "审批必须复用原 action_id，否则 pending 成孤儿、按原 id 回滚失败")


def test_execute_action_accepts_action_id_param():
    """execute_action 需暴露可选 action_id 形参（审批复用的契约）。"""
    import inspect
    assert "action_id" in inspect.signature(A.execute_action).parameters
