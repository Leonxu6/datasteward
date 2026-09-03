from dm.app import data


def _call(fn):
    return getattr(fn, "__wrapped__", fn)()


def test_flink_probe_redacts_backend_exception(monkeypatch):
    import requests

    def boom(*args, **kwargs):
        raise RuntimeError("token=super-secret")

    monkeypatch.setattr(requests, "get", boom)
    result = _call(data.flink_status)
    assert result["ok"] is False
    assert "super-secret" not in result["error"]
    assert "RuntimeError" in result["error"]


def test_warehouse_probe_redacts_backend_exception(monkeypatch):
    from dm.warehouse import store

    def boom():
        raise RuntimeError("password=warehouse-secret")

    monkeypatch.setattr(store, "connect_ro", boom)
    result = _call(data.wh_health)
    assert result["ok"] is False
    assert "warehouse-secret" not in result["error"]
    assert "RuntimeError" in result["error"]
