from types import SimpleNamespace
import json

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


@pytest.mark.parametrize(
    "field,value",
    [
        ("dimensions", " material_id"),
        ("filters", "x='1' "),
        ("filters", "x='1'\n"),
        ("dimensions", "material\u200did"),
        ("filters", "x='1'\ud800"),
        ("filters", "x" * 4001),
    ],
)
def test_query_metric_rejects_padded_controlled_or_oversized_query_text(monkeypatch, field, value):
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


def test_query_metric_rejects_nonstandard_json_numbers(monkeypatch):
    _authorized_metric(monkeypatch)
    cursor = SimpleNamespace(description=[("value",)], fetchall=lambda: [(float("nan"),)], close=lambda: None)
    connection = SimpleNamespace(execute=lambda sql: cursor, close=lambda: None)
    monkeypatch.setattr(metrics_tool, "connect_ro", lambda: connection)

    result = metrics_tool.query_metric(_principal(), "sample")

    assert result == "ERROR: 指标查询失败，请检查数据服务状态或联系维护者。"
    assert "NaN" not in result


def test_list_metrics_rejects_nonstandard_json_numbers(monkeypatch):
    audit_calls = []
    monkeypatch.setattr(metrics_tool, "metric_catalog", lambda: {"bad": float("nan")})
    monkeypatch.setattr(metrics_tool, "audit_event", lambda *args, **kwargs: audit_calls.append((args, kwargs)))

    result = metrics_tool.list_metrics(_principal())

    assert result == "ERROR: 指标目录不可用，请检查指标配置或联系维护者。"
    assert "NaN" not in result
    assert audit_calls
    assert audit_calls[-1][0][7] is False


def test_list_metrics_survives_audit_persistence_failure(monkeypatch):
    catalog = {"stock": {"unit": "pcs"}}
    monkeypatch.setattr(metrics_tool, "metric_catalog", lambda: catalog)
    monkeypatch.setattr(
        metrics_tool,
        "audit_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit down")),
    )

    assert json.loads(metrics_tool.list_metrics(_principal())) == catalog


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


@pytest.mark.parametrize(
    ("columns", "rows", "message"),
    [
        (["value", "value"], [(1, 2)], "duplicate"),
        (["value", ""], [(1, 2)], "non-empty strings"),
        ([" value"], [(1,)], "clean non-empty"),
        (["value\u200dhidden"], [(1,)], "unsafe control"),
        (["x" * 257], [(1,)], "at most 256"),
        (["a", "b"], [(1,)], "row length"),
        (["a"], [object()], "sized sequences"),
        (["a", "b"], ["ab"], "non-text positional"),
        (["a", "b"], [b"ab"], "non-text positional"),
        (["a", "b"], [{"a": 1, "b": 2}], "non-text positional"),
    ],
)
def test_rows_to_records_rejects_malformed_results(columns, rows, message):
    with pytest.raises(ValueError, match=message):
        metrics_tool._rows_to_records(columns, rows)


def test_rows_to_records_preserves_valid_rows():
    assert metrics_tool._rows_to_records(["id", "amount"], [("A", 12)]) == [{"id": "A", "amount": 12}]


def test_query_metric_redacts_database_details_from_user_response(monkeypatch):
    _authorized_metric(monkeypatch)
    audit_calls = []
    monkeypatch.setattr(metrics_tool, "audit_event", lambda *args, **kwargs: audit_calls.append((args, kwargs)))
    secret_error = "password=super-secret host=internal-db"
    monkeypatch.setattr(metrics_tool, "connect_ro", lambda: (_ for _ in ()).throw(RuntimeError(secret_error)))

    result = metrics_tool.query_metric(_principal(), "sample")
    assert result == "ERROR: 指标查询失败，请检查数据服务状态或联系维护者。"
    assert "super-secret" not in result
    assert any(secret_error in str(call) for call in audit_calls)


def test_successful_metric_query_survives_audit_persistence_failure(monkeypatch):
    _authorized_metric(monkeypatch)
    cursor = SimpleNamespace(description=[("value",)], fetchall=lambda: [(1,)], close=lambda: None)
    connection = SimpleNamespace(execute=lambda sql: cursor, close=lambda: None)
    monkeypatch.setattr(metrics_tool, "connect_ro", lambda: connection)
    monkeypatch.setattr(
        metrics_tool,
        "audit_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit down")),
    )

    result = json.loads(metrics_tool.query_metric(_principal(), "sample"))

    assert result["rows"] == [{"value": 1}]
    assert result["audit_warning"] == "metric query completed but audit persistence failed"


def test_metric_validation_error_survives_audit_persistence_failure(monkeypatch):
    monkeypatch.setattr(
        metrics_tool,
        "audit_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit down")),
    )

    result = metrics_tool.query_metric(_principal(), "sample", dimensions=None)

    assert result.startswith("ERROR:")
    assert "must be text" in result
