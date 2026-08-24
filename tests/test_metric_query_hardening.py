import pytest

from dm.ontology.metrics import compile_metric


@pytest.mark.parametrize("name", [None, 3, [], "", " total_stock", "total_stock\n"])
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
