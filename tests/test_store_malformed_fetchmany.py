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
    with pytest.raises(TypeError):
        result.fetchmany(10)
    assert cursor.closed
