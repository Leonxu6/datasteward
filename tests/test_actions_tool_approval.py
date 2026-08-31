from unittest.mock import patch

from dm.tools.actions_tool import execute_action
from dm.tools.principal import Principal


def test_non_boolean_approval_flags_never_reach_action_executor():
    principal = Principal(user="alice", role="仓管")
    for approve in (1, 0, "true", "false", None, []):
        with patch("dm.ontology.actions.execute_action") as executor, patch(
            "dm.tools.actions_tool.audit_event"
        ) as audit:
            result = execute_action(principal, "adjust_safety_stock", material_id="M1", new_value=5, approve=approve)
        assert result == "ERROR: approve 必须是布尔值"
        executor.assert_not_called()
        audit.assert_not_called()


def test_real_boolean_flags_still_reach_executor():
    principal = Principal(user="alice", role="仓管")
    with patch("dm.ontology.actions.execute_action", return_value={"ok": False, "status": "pending"}) as executor, patch(
        "dm.tools.actions_tool.audit_event"
    ):
        execute_action(principal, "adjust_safety_stock", material_id="M1", new_value=5, approve=False)
    assert executor.call_args.kwargs["approve"] is False
