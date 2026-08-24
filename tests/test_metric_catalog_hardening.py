import pytest

from dm.ontology.metrics import _normalize_catalog


def _entry(name="metric_one"):
    return {"name": name, "agg": "sum", "expr": "amount", "base_model": "fact_sales"}


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        "metrics",
        {"metrics": {}},
        {"metrics": "not-a-list"},
        {"metrics": [None]},
        {"metrics": ["metric"]},
    ],
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
