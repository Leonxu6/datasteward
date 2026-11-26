import pytest

from dm.warehouse.store import _Result


class MalformedCursor:
    description = (("id",),)

    def __init__(self):
        self.closed = False

    def fetchmany(self, size):
        return None

    def close(self):
        self.closed = True


def test_malformed_fetchmany_result_still_closes_cursor():
    cursor = MalformedCursor()
    result = _Result(cursor)
    with pytest.raises(TypeError, match="invalid row batch"):
        result.fetchmany(10)
    assert cursor.closed


def test_oversized_fetchmany_result_is_rejected_and_closes_cursor():
    cursor = MalformedCursor()
    cursor.fetchmany = lambda size: [(index,) for index in range(size + 1)]

    with pytest.raises(RuntimeError, match="more than the requested 2 rows"):
        _Result(cursor).fetchmany(2)

    assert cursor.closed
