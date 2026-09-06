from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

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


def test_audit_event_sanitizes_and_bounds_scalar_text(monkeypatch):
    captured = {}
    monkeypatch.setattr(audit, "append_log", lambda name, record: captured.update(name=name, record=record))

    # Principal construction already validates these fields. A lightweight object exercises
    # the audit writer's defense-in-depth boundary independently of Principal validation.
    principal = SimpleNamespace(
        user="tester\u200cname",
        role="role\nname",
        purpose="purpose\u206avalue",
        session_id="s\u206aid",
        channel="cli",
    )
    audit.audit_event(
        principal,
        "query\u200ctool",
        {},
        "SELECT 1\n" + "x" * 20_000,
        [],
        0,
        0,
        False,
        error="backend\u200cerror\n" + "e" * 20_000,
    )

    record = captured["record"]
    assert record["user"] == "tester name"
    assert record["role"] == "role name"
    assert record["purpose"] == "purpose value"
    assert record["session_id"] == "s id"
    assert record["tool_name"] == "query tool"
    assert "\n" not in record["sql"] and len(record["sql"]) <= 10_000
    assert "\n" not in record["error"] and len(record["error"]) <= 10_000
