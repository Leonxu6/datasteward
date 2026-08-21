from datetime import datetime
from decimal import Decimal

from dm.tools import audit
from dm.tools.principal import Principal


def test_audit_event_serializes_complex_args_and_normalizes_fields(monkeypatch):
    captured = {}
    monkeypatch.setattr(audit, "append_log", lambda name, record: captured.update(name=name, record=record))
    monkeypatch.setattr(audit.time, "time", lambda: 10.25)

    principal = Principal(user="tester", role="仓管", session_id="s1", channel="cli")
    audit.audit_event(
        principal,
        "query",
        {"amount": Decimal("1.25"), "when": datetime(2026, 8, 21, 17, 0)},
        None,
        ["orders", 7],
        2,
        10.0,
        True,
        markings=["PII"],
    )

    record = captured["record"]
    assert captured["name"] == "audit_log"
    assert '"amount": "1.25"' in record["tool_args"]
    assert record["tables_touched"] == "orders,7"
    assert record["markings"] == "PII"
    assert record["sql"] == ""
    assert record["duration_ms"] == 250
    assert record["ok"] is True
