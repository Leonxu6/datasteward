import pytest

import dm.ontology.metrics as metrics
from dm.ontology.metrics import compile_metric


def _metric_definition(**overrides):
    definition = {
        "name": "sample_metric",
        "agg": "sum",
        "expr": "amount",
        "base_model": "fact_sales",
        "dimensions": ["customer_id"],
    }
    definition.update(overrides)
    return definition


@pytest.mark.parametrize("name", [None, 3, [], "", " total_stock", "total_stock\n", "bad-name"])
def test_compile_metric_rejects_invalid_metric_names(name):
    with pytest.raises(ValueError):
        compile_metric(name)


@pytest.mark.parametrize("dimensions", ["material_id", {"material_id"}, [3], [None]])
def test_compile_metric_rejects_invalid_dimension_containers(dimensions):
    with pytest.raises(ValueError):
        compile_metric("total_stock", dimensions=dimensions)


@pytest.mark.parametrize("filters", ["material_id='M1'", {"x"}, [3], [None]])
def test_compile_metric_rejects_invalid_filter_containers(filters):
    with pytest.raises(ValueError):
        compile_metric("total_stock", filters=filters)


@pytest.mark.parametrize("limit", [True, False, 0, -1, 501, 1.5, "10", None])
def test_compile_metric_rejects_invalid_limits(limit):
    with pytest.raises(ValueError):
        compile_metric("total_stock", limit=limit)


def test_compile_metric_deduplicates_dimensions_preserving_order():
    sql, _ = compile_metric(
        "total_stock",
        dimensions=["material_id", "material_name", "material_id", " material_name "],
    )
    assert sql.count("`material_id`") == 2
    assert sql.count("`material_name`") == 2
    assert "GROUP BY `material_id`, `material_name`" in sql


@pytest.mark.parametrize(
    ("field", "value"),
    [("expr", "amount;DROP"), ("base_model", "fact sales"), ("dimensions", ["customer_id", "bad-dimension"])],
)
def test_compile_metric_rejects_unsafe_definition_identifiers(monkeypatch, field, value):
    definition = _metric_definition()
    definition[field] = value
    monkeypatch.setattr(metrics, "_CACHE", {"sample_metric": definition})
    with pytest.raises(ValueError):
        compile_metric("sample_metric")


@pytest.mark.parametrize(
    "default_filters",
    ["customer_id='C1'", ["customer_id='C1'; DROP TABLE x"], ["customer_id='C1'\n"], ["secret='x'"], [3]],
)
def test_compile_metric_rejects_invalid_default_filters(monkeypatch, default_filters):
    monkeypatch.setattr(metrics, "_CACHE", {"sample_metric": _metric_definition(default_filters=default_filters)})
    with pytest.raises(ValueError):
        compile_metric("sample_metric")


def test_compile_metric_accepts_valid_default_filters(monkeypatch):
    monkeypatch.setattr(metrics, "_CACHE", {"sample_metric": _metric_definition(default_filters=["customer_id='C1'"])})
    sql, _ = compile_metric("sample_metric")
    assert "WHERE (customer_id='C1')" in sql


@pytest.mark.parametrize("agg", [None, 3, "", " sum", "sum ", "median"])
def test_compile_metric_rejects_invalid_aggregate_definitions(monkeypatch, agg):
    monkeypatch.setattr(metrics, "_CACHE", {"sample_metric": _metric_definition(agg=agg)})
    with pytest.raises(ValueError):
        compile_metric("sample_metric")


def test_compile_metric_normalizes_aggregate_case(monkeypatch):
    monkeypatch.setattr(metrics, "_CACHE", {"sample_metric": _metric_definition(agg="AVG")})
    sql, _ = compile_metric("sample_metric")
    assert "AVG(`amount`)" in sql


def test_compile_metric_deduplicates_default_and_requested_filters(monkeypatch):
    definition = _metric_definition(default_filters=["customer_id='C1'"])
    monkeypatch.setattr(metrics, "_CACHE", {"sample_metric": definition})
    sql, _ = compile_metric(
        "sample_metric",
        filters=["customer_id='C1'", "customer_id='C2'", "customer_id='C1'"],
    )
    assert sql.count("(customer_id='C1')") == 1
    assert sql.count("(customer_id='C2')") == 1
    assert sql.index("(customer_id='C1')") < sql.index("(customer_id='C2')")
