from unittest.mock import patch

from dm.tools.actions_tool import execute_action
from dm.tools.principal import Principal


def test_malformed_action_results_fail_closed_and_are_audited():
    principal = Principal(user="alice", role="仓管")
    invalid = (None, [], "ok", {}, {"ok": 1}, {"ok": True, "target": 7}, {"ok": False, "error": 7})
    for result in invalid:
        with patch("dm.ontology.actions.execute_action", return_value=result), patch(
            "dm.tools.actions_tool.audit_event"
        ) as audit:
            response = execute_action(principal, "adjust_safety_stock", material_id="M1", new_value=5)
        assert response == "ERROR: Action 执行失败"
        assert audit.call_count == 1
        assert audit.call_args.kwargs["decision"] == "error"


def test_valid_failed_action_result_uses_deny_audit_decision():
    principal = Principal(user="alice", role="仓管")
    with patch(
        "dm.ontology.actions.execute_action",
        return_value={"ok": False, "target": "material", "error": "approval required"},
    ), patch("dm.tools.actions_tool.audit_event") as audit:
        response = execute_action(principal, "adjust_safety_stock", material_id="M1", new_value=5)
    assert '"ok": false' in response
    assert audit.call_args.kwargs["decision"] == "deny"
