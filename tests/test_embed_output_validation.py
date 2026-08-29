import pytest

from dm.docs import embed


def test_validated_vector_requires_exact_finite_dimension(monkeypatch):
    monkeypatch.setattr(embed, "DIM", 3)
    assert embed._validated_vector([1, 2.5, "3"]) == [1.0, 2.5, 3.0]
    for value in (None, "123", [1, 2], [1, 2, 3, 4], [1, float("nan"), 3], [1, True, 3], [1, object(), 3]):
        with pytest.raises(RuntimeError):
            embed._validated_vector(value)


def test_validated_vectors_requires_one_vector_per_text(monkeypatch):
    monkeypatch.setattr(embed, "DIM", 2)
    assert embed._validated_vectors([[1, 2], [3, 4]], expected=2) == [[1.0, 2.0], [3.0, 4.0]]
    with pytest.raises(RuntimeError, match="fewer"):
        embed._validated_vectors([[1, 2]], expected=2)
    with pytest.raises(RuntimeError, match="more"):
        embed._validated_vectors([[1, 2], [3, 4], [5, 6]], expected=2)
    with pytest.raises(RuntimeError, match="iterable"):
        embed._validated_vectors(None, expected=1)
