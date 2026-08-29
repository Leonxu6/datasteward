import pytest

from dm.tools.audit_record import _MAX_LABELS, join_labels


def test_join_labels_rejects_oversized_generators_without_materializing_them():
    consumed = 0

    def labels():
        nonlocal consumed
        for index in range(10_000):
            consumed += 1
            yield f"label-{index}"

    with pytest.raises(ValueError, match="at most"):
        join_labels(labels())

    assert consumed == _MAX_LABELS + 1
