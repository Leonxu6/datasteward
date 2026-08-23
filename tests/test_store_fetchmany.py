import pytest

from dm.warehouse.store import _Result


class Cursor:
    description = (("id",),)

    def __init__(self, rows=None):
        self.calls = []
        self.closed = False
        self.rows = [] if rows is None else rows

    def fetchmany(self, size):
        self.calls.append(size)
        return self.rows

    def close(self):
        self.closed = True


def test_fetchmany_normalizes_valid_size_and_closes_on_exhaustion():
    cursor = Cursor()
    result = _Result(cursor)
    assert result.fetchmany(5) == []
    assert cursor.calls == [5]
    assert cursor.closed


def test_fetchmany_closes_after_partial_final_batch():
    cursor = Cursor([(1,), (2,)])
    result = _Result(cursor)
    assert result.fetchmany(5) == [(1,), (2,)]
    assert cursor.calls == [5]
    assert cursor.closed


def test_fetchmany_keeps_cursor_open_for_full_batch():
    cursor = Cursor([(1,), (2,)])
    result = _Result(cursor)
    assert result.fetchmany(2) == [(1,), (2,)]
    assert not cursor.closed


@pytest.mark.parametrize("size", [True, 0, -1, 1.5, "10", None])
def test_fetchmany_rejects_invalid_size_before_driver_call(size):
    cursor = Cursor()
    result = _Result(cursor)
    with pytest.raises(ValueError):
        result.fetchmany(size)
    assert cursor.calls == []
    assert not cursor.closed
