from dm.ontology import actions as A
from dm.security import User


def test_approve_uses_latest_action_state(monkeypatch):
    """A completed action must not be replayed from its older pending record."""
    records = [
        {
            "action_id": "ACT-REPLAY-1",
            "status": "pending",
            "action": "adjust_safety_stock",
            "params": {"material_id": "M0001", "new_value": 30},
        },
        {
            "action_id": "ACT-REPLAY-1",
            "status": "executed",
            "action": "adjust_safety_stock",
            "params": {"material_id": "M0001", "new_value": 30},
        },
    ]
    monkeypatch.setattr(A, "read_log", lambda name: records if name == "action_log" else [])
    executed = []
    monkeypatch.setattr(A, "execute_action", lambda *args, **kwargs: executed.append((args, kwargs)))

    result = A.approve_action("ACT-REPLAY-1", user=User("审批人", "管理层"))

    assert result == {"ok": False, "error": "该 Action 状态为 executed，不可审批"}
    assert executed == []


def test_approve_tolerates_unrelated_malformed_log_records(monkeypatch):
    records = [
        {"status": "pending"},
        {
            "action_id": "ACT-VALID-1",
            "status": "pending",
            "action": "adjust_safety_stock",
            "params": {"material_id": "M0001", "new_value": 30},
        },
    ]
    monkeypatch.setattr(A, "read_log", lambda name: records if name == "action_log" else [])
    monkeypatch.setattr(
        A,
        "execute_action",
        lambda *args, **kwargs: {"ok": True, "action_id": kwargs["action_id"]},
    )

    assert A.approve_action("ACT-VALID-1", user=User("审批人", "管理层")) == {
        "ok": True,
        "action_id": "ACT-VALID-1",
    }


def test_approve_rejects_matching_record_without_executable_fields(monkeypatch):
    records = [{"action_id": "ACT-BROKEN-1", "status": "pending"}]
    monkeypatch.setattr(A, "read_log", lambda name: records if name == "action_log" else [])
    executed = []
    monkeypatch.setattr(A, "execute_action", lambda *args, **kwargs: executed.append((args, kwargs)))

    assert A.approve_action("ACT-BROKEN-1", user=User("审批人", "管理层")) == {
        "ok": False,
        "error": "Action 审批记录无效，已拒绝执行",
    }
    assert executed == []


def test_approve_rejects_unknown_persisted_action(monkeypatch):
    records = [{
        "action_id": "ACT-BROKEN-2",
        "status": "pending",
        "action": "unregistered_action",
        "params": {},
    }]
    monkeypatch.setattr(A, "read_log", lambda name: records if name == "action_log" else [])
    executed = []
    monkeypatch.setattr(A, "execute_action", lambda *args, **kwargs: executed.append((args, kwargs)))

    assert A.approve_action("ACT-BROKEN-2", user=User("审批人", "管理层")) == {
        "ok": False,
        "error": "Action 审批记录无效，已拒绝执行",
    }
    assert executed == []
