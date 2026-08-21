import pytest

from dm.warehouse import store


def test_store_log_round_trip_uses_configured_log_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LOG_DIR", tmp_path)
    store.append_log("audit_log", {"id": 1})
    store.append_log("audit_log", {"id": 2})
    assert store.read_log("audit_log") == [{"id": 1}, {"id": 2}]


@pytest.mark.parametrize("name", ["../audit", "nested/audit", ".hidden", "has space", ""])
def test_store_log_rejects_paths_outside_log_directory(tmp_path, monkeypatch, name):
    monkeypatch.setattr(store, "LOG_DIR", tmp_path)
    with pytest.raises(ValueError):
        store.append_log(name, {"id": 1})
    with pytest.raises(ValueError):
        store.read_log(name)
