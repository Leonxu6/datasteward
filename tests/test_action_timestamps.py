from datetime import datetime, timezone

from dm.ontology import actions
from dm.security import User


def _assert_utc(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def test_action_audit_and_history_records_use_aware_utc_timestamps(monkeypatch):
    records = []
    monkeypatch.setattr(actions, "append_log", lambda name, record: records.append((name, record)))
    user = User("alice", "管理层")

    actions._audit_action("ACT1", "adjust_safety_stock", {}, user, "allow", "ok")
    actions._record(
        "ACT1",
        "adjust_safety_stock",
        {},
        user,
        table="material",
        op="update",
        pk_col="material_id",
        pk_val="M1",
        before={"safety_stock": 1},
        after={"safety_stock": 2},
        status="executed",
    )

    assert [name for name, _record in records] == ["audit_log", "action_log"]
    for _name, record in records:
        _assert_utc(record["ts"])
