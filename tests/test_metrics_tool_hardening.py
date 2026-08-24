from types import SimpleNamespace

import pytest

import dm.tools.metrics_tool as metrics_tool


def _principal():
    return SimpleNamespace(role="analyst", purpose="test", to_user=lambda: object())


def _authorized_metric(monkeypatch):
    monkeypatch.setattr(metrics_tool, "audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(metrics_tool, "effective_user_markings", lambda user: set())
    monkeypatch.setattr(
        metrics_tool,
        "compile_metric",
        lambda *args, **kwargs: ("SELECT 1", {"base_model": "fact", "required_markings": []}),
    )


@pytest.mark.parametrize("field,value", [("dimensions", None), ("dimensions", 3), ("filters", []), ("filters", 4)])
def test_query_metric_rejects_non_text_query_arguments(monkeypatch, field, value):
    monkeypatch.setattr(metrics_tool, "audit_event", lambda *args, **kwargs: None)
    result = metrics_tool.query_metric(_principal(), "total_stock", **{field: value})
    assert result.startswith("ERROR:")
    assert "must be text" in result


@pytest.mark.parametrize("field,value", [("dimensions", " material_id"), ("filters", "x='1' "), ("filters", "x='1'\n")])
def test_query_metric_rejects_padded_or_controlled_query_text(monkeypatch, field, value):
    monkeypatch.setattr(metrics_tool, "audit_event", lambda *args, **kwargs: None)
    result = metrics_tool.query_metric(_principal(), "total_stock", **{field: value})
    assert result.startswith("ERROR:")


def test_query_metric_closes_cursor_and_connection_after_success(monkeypatch):
    _authorized_metric(monkeypatch)
    cursor = SimpleNamespace(description=[("value",)], fetchall=lambda: [(1,)], close=lambda: None)
    cursor.closed = False
    cursor.close = lambda: setattr(cursor, "closed", True)
    connection = SimpleNamespace(execute=lambda sql: cursor, close=lambda: None)
    connection.closed = False
    connection.close = lambda: setattr(connection, "closed", True)
    monkeypatch.setattr(metrics_tool, "connect_ro", lambda: connection)

    result = metrics_tool.query_metric(_principal(), "sample")
    assert '"value": 1' in result
    assert cursor.closed is True
    assert connection.closed is True


def test_query_metric_closes_resources_after_fetch_failure(monkeypatch):
    _authorized_metric(monkeypatch)
    cursor = SimpleNamespace(description=[("value",)], close=lambda: None)
    cursor.closed = False
    cursor.close = lambda: setattr(cursor, "closed", True)
    cursor.fetchall = lambda: (_ for _ in ()).throw(RuntimeError("read failed"))
    connection = SimpleNamespace(execute=lambda sql: cursor, close=lambda: None)
    connection.closed = False
    connection.close = lambda: setattr(connection, "closed", True)
    monkeypatch.setattr(metrics_tool, "connect_ro", lambda: connection)

    result = metrics_tool.query_metric(_principal(), "sample")
    assert result.startswith("ERROR:")
    assert cursor.closed is True
    assert connection.closed is True
