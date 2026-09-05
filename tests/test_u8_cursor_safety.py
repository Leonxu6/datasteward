from dm.connect import u8_mapping
from dm.connect.base import ColumnDef, DatasetDef


class FakeConnector:
    def introspect(self):
        return [
            DatasetDef(
                name="Inventory",
                columns=[ColumnDef(name="cInvCode", data_type="nvarchar")],
                primary_key=["cInvCode"],
            )
        ]

    def read_table(self, name, cursor_col=None, since=None):
        return ["cInvCode"], [("A001",)]


class FakeWarehouse:
    def __init__(self):
        self.executed = []
        self.executemany_calls = []
        self.closed = False

    def execute(self, sql):
        self.executed.append(sql)
        return self

    def executemany(self, sql, values):
        self.executemany_calls.append((sql, values))

    def close(self):
        self.closed = True


def test_missing_incremental_cursor_fails_before_row_insert(monkeypatch):
    warehouse = FakeWarehouse()
    saved = {}
    monkeypatch.setattr(u8_mapping, "get_connector", lambda name: FakeConnector())
    monkeypatch.setattr(u8_mapping, "connect_admin", lambda db: warehouse)
    monkeypatch.setattr(u8_mapping, "_load_wm", lambda: {"Inventory": "2026-08-20"})
    monkeypatch.setattr(u8_mapping, "_save_wm", lambda wm: saved.update(wm))
    monkeypatch.setattr(u8_mapping, "audit_event", lambda *args, **kwargs: None)

    report = u8_mapping.sync(tables=["Inventory"], verbose=False)

    assert "游标列" in report["Inventory"]
    assert warehouse.executemany_calls == []
    assert warehouse.closed
    assert saved == {"Inventory": "2026-08-20"}


def test_full_refresh_validates_rows_before_truncating_target(monkeypatch):
    warehouse = FakeWarehouse()
    saved = {}
    dataset = DatasetDef(
        name="CurrentStock",
        columns=[ColumnDef(name="cInvCode", data_type="nvarchar")],
        primary_key=["cInvCode"],
    )

    class MalformedConnector:
        def introspect(self):
            return [dataset]

        def read_table(self, name, cursor_col=None, since=None):
            return ["cInvCode"], [("A001", "unexpected")]

    monkeypatch.setattr(u8_mapping, "get_connector", lambda name: MalformedConnector())
    monkeypatch.setattr(u8_mapping, "connect_admin", lambda db: warehouse)
    monkeypatch.setattr(u8_mapping, "_load_wm", lambda: {})
    monkeypatch.setattr(u8_mapping, "_save_wm", lambda wm: saved.update(wm))
    monkeypatch.setattr(u8_mapping, "audit_event", lambda *args, **kwargs: None)

    report = u8_mapping.sync(tables=["CurrentStock"], verbose=False)

    assert "行宽" in report["CurrentStock"]
    assert not any(sql.startswith("TRUNCATE TABLE") for sql in warehouse.executed)
    assert warehouse.executemany_calls == []
    assert warehouse.closed
    assert saved == {}


def test_incremental_sync_rejects_unintrospected_columns_before_insert(monkeypatch):
    warehouse = FakeWarehouse()
    saved = {"Inventory": "2026-08-20"}
    dataset = DatasetDef(
        name="Inventory",
        columns=[
            ColumnDef(name="cInvCode", data_type="nvarchar"),
            ColumnDef(name="dModifyDate", data_type="datetime"),
        ],
        primary_key=["cInvCode"],
    )

    class MalformedConnector:
        def introspect(self):
            return [dataset]

        def read_table(self, name, cursor_col=None, since=None):
            return ["cInvCode", "dModifyDate", "unexpected"], [("A001", "2026-09-05", "x")]

    monkeypatch.setattr(u8_mapping, "get_connector", lambda name: MalformedConnector())
    monkeypatch.setattr(u8_mapping, "connect_admin", lambda db: warehouse)
    monkeypatch.setattr(u8_mapping, "_load_wm", lambda: saved.copy())
    monkeypatch.setattr(u8_mapping, "_save_wm", lambda wm: saved.update(wm))
    monkeypatch.setattr(u8_mapping, "audit_event", lambda *args, **kwargs: None)

    report = u8_mapping.sync(tables=["Inventory"], verbose=False)

    assert "未自省列" in report["Inventory"]
    assert warehouse.executemany_calls == []
    assert warehouse.closed
    assert saved == {"Inventory": "2026-08-20"}
