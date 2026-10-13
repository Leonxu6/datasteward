from datetime import datetime, timezone

from dm.connect import u8_mapping
from dm.connect.base import ColumnDef, DatasetDef


def test_sync_persists_a_utc_derived_naive_starrocks_timestamp(monkeypatch):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is timezone.utc
            return cls(2026, 10, 13, 9, 45, 12, 123456, tzinfo=timezone.utc)

    dataset = DatasetDef(
        name="CurrentStock",
        columns=[ColumnDef(name="cInvCode", data_type="nvarchar")],
        primary_key=["cInvCode"],
    )

    class Connector:
        def introspect(self):
            return [dataset]

        def read_table(self, name, cursor_col=None, since=None):
            return ["cInvCode"], [("A001",)]

    class Warehouse:
        def __init__(self):
            self.values = []
            self.closed = False

        def execute(self, _statement):
            return self

        def executemany(self, _statement, values):
            self.values.extend(values)

        def close(self):
            self.closed = True

    warehouse = Warehouse()
    monkeypatch.setattr(u8_mapping, "datetime", FrozenDateTime)
    monkeypatch.setattr(u8_mapping, "get_connector", lambda _name: Connector())
    monkeypatch.setattr(u8_mapping, "connect_admin", lambda _database: warehouse)
    monkeypatch.setattr(u8_mapping, "_load_wm", lambda: {})
    monkeypatch.setattr(u8_mapping, "_save_wm", lambda _watermark: None)
    monkeypatch.setattr(u8_mapping, "audit_event", lambda *args, **kwargs: None)

    assert u8_mapping.sync(tables=["CurrentStock"], verbose=False) == {"CurrentStock": 1}
    assert warehouse.values == [("A001", datetime(2026, 10, 13, 9, 45, 12))]
    assert warehouse.values[0][-1].tzinfo is None
    assert warehouse.closed
