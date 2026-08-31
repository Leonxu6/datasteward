import json
from unittest.mock import patch

from dm.tools.actions_tool import execute_action
from dm.tools.principal import Principal


def test_successful_action_is_not_reported_as_failed_when_audit_write_breaks():
    principal = Principal(user="alice", role="仓管")
    with patch(
        "dm.ontology.actions.execute_action",
        return_value={"ok": True, "target": "material:M1", "action_id": "ACT-1"},
    ) as executor, patch("dm.tools.actions_tool.audit_event", side_effect=RuntimeError("disk full")):
        response = json.loads(execute_action(principal, "adjust_safety_stock", material_id="M1", new_value=5, approve=True))

    assert executor.call_count == 1
    assert response["ok"] is True
    assert response["action_id"] == "ACT-1"
    assert response["audit_ok"] is False
    assert "completed" in response["audit_warning"]


def test_executor_failure_stays_stable_when_error_audit_also_fails():
    principal = Principal(user="alice", role="仓管")
    with patch("dm.ontology.actions.execute_action", side_effect=RuntimeError("db secret")), patch(
        "dm.tools.actions_tool.audit_event", side_effect=RuntimeError("audit storage unavailable")
    ):
        assert execute_action(principal, "adjust_safety_stock", approve=True) == "ERROR: Action 执行失败"
