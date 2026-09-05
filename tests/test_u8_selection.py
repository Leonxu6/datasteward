from types import SimpleNamespace

import pytest

from dm.connect import u8_mapping


def test_sync_rejects_unknown_requested_table_before_external_connections(monkeypatch):
    get_connector_called = False

    def fail_get_connector(*args, **kwargs):
        nonlocal get_connector_called
        get_connector_called = True
        raise AssertionError("connector should not be touched")

    monkeypatch.setattr(u8_mapping, "get_connector", fail_get_connector)
    with pytest.raises(ValueError, match="unknown table"):
        u8_mapping.sync(tables=["Inventroy"], verbose=False)
    assert not get_connector_called


def test_sync_deduplicates_valid_requested_tables(monkeypatch):
    captured = {}

    class FakeConnector:
        def introspect(self):
            return []

    class FakeWarehouse:
        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(u8_mapping, "get_connector", lambda name: FakeConnector())
    monkeypatch.setattr(u8_mapping, "connect_admin", lambda db: FakeWarehouse())
    monkeypatch.setattr(u8_mapping, "_load_wm", lambda: {})
    monkeypatch.setattr(u8_mapping, "_save_wm", lambda wm: captured.setdefault("wm", wm.copy()))
    monkeypatch.setattr(u8_mapping, "audit_event", lambda *args, **kwargs: None)

    report = u8_mapping.sync(tables=["Inventory", "Inventory"], verbose=False)
    assert report == {"Inventory": "源库无此表"}
    assert captured["closed"]
    assert captured["wm"] == {}


def test_sync_redacts_backend_errors_from_report_and_audit(monkeypatch):
    captured = {"audits": []}
    dataset = SimpleNamespace(
        name="Inventory",
        columns=[SimpleNamespace(name="id", data_type="int")],
        primary_key=["id"],
    )

    class FakeConnector:
        def introspect(self):
            return [dataset]

        def read_table(self, *args, **kwargs):
            raise RuntimeError("mssql://user:password=secret@internal-host/db")

    class FakeWarehouse:
        def execute(self, sql):
            return None

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(u8_mapping, "get_connector", lambda name: FakeConnector())
    monkeypatch.setattr(u8_mapping, "connect_admin", lambda db: FakeWarehouse())
    monkeypatch.setattr(u8_mapping, "_load_wm", lambda: {})
    monkeypatch.setattr(u8_mapping, "_save_wm", lambda wm: captured.setdefault("wm", wm.copy()))
    monkeypatch.setattr(
        u8_mapping,
        "audit_event",
        lambda *args, **kwargs: captured["audits"].append((args, kwargs)),
    )

    report = u8_mapping.sync(tables=["Inventory"], verbose=False)

    assert report == {"Inventory": "失败: RuntimeError"}
    assert "secret" not in repr(report)
    assert captured["closed"]
    assert captured["wm"] == {}
    assert len(captured["audits"]) == 1
    audit_args, audit_kwargs = captured["audits"][0]
    assert audit_args[8] == "RuntimeError"
    assert "secret" not in repr((audit_args, audit_kwargs))


def test_status_closes_warehouse_and_redacts_query_failures(monkeypatch, capsys):
    captured = {}

    class FakeWarehouse:
        def execute(self, sql):
            raise RuntimeError("mysql://user:password=secret@warehouse/internal")

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(u8_mapping, "_load_wm", lambda: {})
    monkeypatch.setattr(u8_mapping, "connect_admin", lambda db: FakeWarehouse())

    u8_mapping.status()

    output = capsys.readouterr().out
    assert captured["closed"]
    assert "RuntimeError" in output
    assert "secret" not in output
    assert "warehouse/internal" not in output
