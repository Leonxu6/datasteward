import pytest

from dm.docs.embed import _dimension


def test_embedding_dimension_accepts_bounded_ascii_integers():
    assert _dimension(1) == 1
    assert _dimension("512") == 512
    assert _dimension(8192) == 8192


@pytest.mark.parametrize("value", [0, -1, 8193, True, 1.5, None, "", " 512", "512 ", "+512", "５１２"])
def test_embedding_dimension_rejects_ambiguous_or_out_of_range_values(value):
    with pytest.raises(ValueError):
        _dimension(value)
