import pytest

import dm.ontology.metrics as metrics
from dm.ontology.metrics import _normalize_catalog, metric_catalog


def _entry(name="metric_one", **overrides):
    value = {
        "name": name,
        "agg": "sum",
        "expr": "amount",
        "base_model": "fact_sales",
        "dimensions": ["customer_id"],
        "required_markings": ["FIN"],
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "raw",
    [None, [], "metrics", {"metrics": {}}, {"metrics": "not-a-list"}, {"metrics": [None]}, {"metrics": ["metric"]}],
)
def test_normalize_catalog_rejects_invalid_shapes(raw):
    with pytest.raises(ValueError):
        _normalize_catalog(raw)


@pytest.mark.parametrize("name", [None, 3, "", " metric", "metric-name", "metric\n"])
def test_normalize_catalog_rejects_invalid_metric_names(name):
    with pytest.raises(ValueError):
        _normalize_catalog({"metrics": [_entry(name)]})


def test_normalize_catalog_rejects_duplicate_metric_names():
    with pytest.raises(ValueError, match="duplicate metric name"):
        _normalize_catalog({"metrics": [_entry("sales"), _entry("sales")]})


def test_normalize_catalog_indexes_valid_entries():
    first = _entry("sales")
    second = _entry("stock")
    assert _normalize_catalog({"metrics": [first, second]}) == {"sales": first, "stock": second}


def test_metric_catalog_returns_isolated_list_metadata(monkeypatch):
    definition = _entry("sales")
    monkeypatch.setattr(metrics, "_CACHE", {"sales": definition})
    result = metric_catalog()
    result[0]["dimensions"].append("mutated")
    result[0]["required_markings"].clear()
    assert definition["dimensions"] == ["customer_id"]
    assert definition["required_markings"] == ["FIN"]


@pytest.mark.parametrize("field,value", [("dimensions", "customer_id"), ("required_markings", "FIN"), ("dimensions", [3])])
def test_metric_catalog_rejects_malformed_list_metadata(monkeypatch, field, value):
    definition = _entry("sales")
    definition[field] = value
    monkeypatch.setattr(metrics, "_CACHE", {"sales": definition})
    with pytest.raises(ValueError):
        metric_catalog()
