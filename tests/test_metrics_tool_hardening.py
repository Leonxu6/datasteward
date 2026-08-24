from types import SimpleNamespace

import pytest

import dm.tools.metrics_tool as metrics_tool


def _principal():
    return SimpleNamespace(role="analyst", purpose="test", to_user=lambda: object())


@pytest.mark.parametrize("field,value", [("dimensions", None), ("dimensions", 3), ("filters", []), ("filters", 4)])
def test_query_metric_rejects_non_text_query_arguments(monkeypatch, field, value):
    monkeypatch.setattr(metrics_tool, "audit_event", lambda *args, **kwargs: None)
    kwargs = {field: value}
    result = metrics_tool.query_metric(_principal(), "total_stock", **kwargs)
    assert result.startswith("ERROR:")
    assert "must be text" in result


@pytest.mark.parametrize("field,value", [("dimensions", " material_id"), ("filters", "x='1' "), ("filters", "x='1'\n")])
def test_query_metric_rejects_padded_or_controlled_query_text(monkeypatch, field, value):
    monkeypatch.setattr(metrics_tool, "audit_event", lambda *args, **kwargs: None)
    result = metrics_tool.query_metric(_principal(), "total_stock", **{field: value})
    assert result.startswith("ERROR:")
