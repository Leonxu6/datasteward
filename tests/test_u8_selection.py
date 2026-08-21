import pytest

from dm.connect import u8_mapping


def test_sync_rejects_unknown_requested_table_before_external_connections(monkeypatch):
    connector = pytest.MonkeyPatch()
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
