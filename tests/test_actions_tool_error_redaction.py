from unittest.mock import patch

from dm.tools.actions_tool import execute_action
from dm.tools.principal import Principal


def test_executor_failures_do_not_expose_backend_exception_details():
    principal = Principal(user="alice", role="仓管")
    with patch(
        "dm.ontology.actions.execute_action",
        side_effect=RuntimeError("postgres://user:secret@db/internal"),
    ), patch("dm.tools.actions_tool.audit_event") as audit:
        response = execute_action(principal, "adjust_safety_stock", material_id="M1", new_value=5)

    assert response == "ERROR: Action 执行失败"
    assert "secret" not in response
    assert audit.call_args.args[8] == "RuntimeError"
    assert "secret" not in audit.call_args.args[8]


def test_error_categories_do_not_depend_on_exception_string_rendering():
    class BrokenError(RuntimeError):
        def __str__(self):
            raise RuntimeError("string rendering failed")

    principal = Principal(user="alice", role="仓管")
    with patch("dm.ontology.actions.execute_action", side_effect=BrokenError()), patch(
        "dm.tools.actions_tool.audit_event"
    ) as audit:
        assert execute_action(principal, "adjust_safety_stock") == "ERROR: Action 执行失败"
    assert audit.call_args.args[8] == "BrokenError"
