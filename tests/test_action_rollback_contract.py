from contextlib import contextmanager

from dm.ontology import actions
from dm.security import User


class _Connection:
    def __init__(self):
        self.calls = []
        self.committed = False
        self.closed = False

    @contextmanager
    def cursor(self):
        connection = self

        class Cursor:
            def execute(self, sql, parameters):
                connection.calls.append((sql, parameters))

        yield Cursor()

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def _record(**overrides):
    record = {
        "action_id": "ACT-1",
        "action": "adjust_safety_stock",
        "status": "executed",
        "rolled_back": False,
        "table": "material",
        "op": "update",
        "pk_col": "material_id",
        "pk_val": "M0001",
        "before": {"safety_stock": 12},
    }
    record.update(overrides)
    return record


def test_rollback_uses_static_contract_sql(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(actions, "read_log", lambda _name: [_record()])
    monkeypatch.setattr(actions, "_pg_conn", lambda: connection)
    monkeypatch.setattr(actions, "can_execute_action", lambda *_args: (True, ""))
    monkeypatch.setattr(actions, "append_log", lambda *_args: None)
    monkeypatch.setattr(actions, "_audit_action", lambda *_args, **_kwargs: None)

    result = actions.rollback_action("ACT-1", user=User("operator", "管理层"))

    assert result["ok"] is True
    assert connection.calls == [
        ("UPDATE material SET safety_stock=%s WHERE material_id=%s", (12, "M0001"))
    ]
    assert connection.committed is True
    assert connection.closed is True


def test_rollback_rejects_log_owned_identifiers_before_connecting(monkeypatch):
    malicious = _record(table="material; DROP TABLE supplier; --")
    monkeypatch.setattr(actions, "read_log", lambda _name: [malicious])
    monkeypatch.setattr(
        actions,
        "_pg_conn",
        lambda: (_ for _ in ()).throw(AssertionError("invalid rollback must not connect")),
    )

    result = actions.rollback_action("ACT-1", user=User("operator", "管理层"))

    assert result == {"ok": False, "error": "Action 回滚记录无效，已拒绝执行"}


def test_rollback_skips_malformed_log_rows(monkeypatch):
    monkeypatch.setattr(actions, "read_log", lambda _name: [None, {"unexpected": True}])

    assert actions.rollback_action("ACT-1", user=User("operator", "管理层")) == {
        "ok": False,
        "error": "未找到可回滚的已执行 Action",
    }
