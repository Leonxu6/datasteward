from dm.tools import audit as audit_module
from dm.tools.principal import Principal


def test_audit_events_record_explicit_utc_offsets(monkeypatch):
    captured = {}

    def fake_append_log(name, record):
        captured["name"] = name
        captured["record"] = record

    monkeypatch.setattr(audit_module, "append_log", fake_append_log)
    audit_module.audit_event(
        Principal(user="tester", role="仓管"),
        "query",
        {},
        "SELECT 1",
        [],
        1,
        0.0,
        True,
    )

    assert captured["name"] == "audit_log"
    assert captured["record"]["ts"].endswith("+00:00")
