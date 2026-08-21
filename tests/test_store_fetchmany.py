import pytest

from dm.warehouse.store import _Result


class Cursor:
    description = (("id",),)

    def __init__(self):
        self.calls = []
        self.closed = False

    def fetchmany(self, size):
        self.calls.append(size)
        return []

    def close(self):
        self.closed = True


def test_fetchmany_normalizes_valid_size_and_closes_on_exhaustion():
    cursor = Cursor()
    result = _Result(cursor)
    assert result.fetchmany(5) == []
    assert cursor.calls == [5]
    assert cursor.closed


@pytest.mark.parametrize("size", [True, 0, -1, 1.5, "10", None])
def test_fetchmany_rejects_invalid_size_before_driver_call(size):
    cursor = Cursor()
    result = _Result(cursor)
    with pytest.raises(ValueError):
        result.fetchmany(size)
    assert cursor.calls == []
    assert not cursor.closed
