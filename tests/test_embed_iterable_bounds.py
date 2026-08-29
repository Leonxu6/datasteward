import pytest

from dm.docs.embed import _MAX_BATCH, _request_texts


def test_embedding_batch_rejects_oversized_generators_without_materializing_them():
    consumed = 0

    def texts():
        nonlocal consumed
        for index in range(10_000):
            consumed += 1
            yield f"text-{index}"

    with pytest.raises(ValueError, match="at most"):
        _request_texts(texts())

    assert consumed == _MAX_BATCH + 1
