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


def test_status_bounds_and_orders_raw_table_discovery(monkeypatch, capsys):
    captured = {"queries": []}

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def fetchmany(self, size):
            captured.setdefault("fetch_sizes", []).append(size)
            return self.rows[:size]

        def fetchone(self):
            return self.rows[0]

    class FakeWarehouse:
        def execute(self, sql):
            captured["queries"].append(sql)
            if "information_schema.tables" in sql:
                return FakeResult([("raw_u8__inventory",)])
            return FakeResult([(3,)])

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(u8_mapping, "_load_wm", lambda: {})
    monkeypatch.setattr(u8_mapping, "connect_admin", lambda db: FakeWarehouse())
    monkeypatch.setattr(u8_mapping, "_MAX_STATUS_TABLES", 2)

    u8_mapping.status()

    output = capsys.readouterr().out
    assert "raw_u8__inventory" in output
    assert "3 行" in output
    assert "ORDER BY table_name LIMIT 3" in captured["queries"][0]
    assert captured["fetch_sizes"] == [3]
    assert captured["closed"]


def test_status_rejects_raw_table_discovery_over_budget(monkeypatch, capsys):
    captured = {}

    class FakeResult:
        def fetchmany(self, size):
            return [("raw_u8__a",), ("raw_u8__b",), ("raw_u8__c",)][:size]

    class FakeWarehouse:
        def execute(self, sql):
            return FakeResult()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(u8_mapping, "_load_wm", lambda: {})
    monkeypatch.setattr(u8_mapping, "connect_admin", lambda db: FakeWarehouse())
    monkeypatch.setattr(u8_mapping, "_MAX_STATUS_TABLES", 2)

    u8_mapping.status()

    output = capsys.readouterr().out
    assert "RuntimeError" in output
    assert "raw_u8__a" not in output
    assert captured["closed"]
