import pytest

from dm.warehouse.validation import normalize_fetch_size


@pytest.mark.parametrize("value", [1, 2, 1000])
def test_fetch_size_accepts_positive_integers(value):
    assert normalize_fetch_size(value) == value


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "10", None])
def test_fetch_size_rejects_bool_nonpositive_and_noninteger_values(value):
    with pytest.raises(ValueError):
        normalize_fetch_size(value)
