import pytest

from dm.warehouse.store import _Conn, _Result


class FakeCursor:
    def __init__(self, rows=(), error=None, fetch_error=None):
        self.description = (("id",),)
        self.rows = list(rows)
        self.error = error
        self.fetch_error = fetch_error
        self.closed = False
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self.error:
            raise self.error

    def executemany(self, sql, params):
        self.executed.append((sql, params))
        if self.error:
            raise self.error

    def fetchone(self):
        if self.fetch_error:
            raise self.fetch_error
        return self.rows.pop(0) if self.rows else None

    def fetchmany(self, size):
        if self.fetch_error:
            raise self.fetch_error
        result, self.rows = self.rows[:size], self.rows[size:]
        return result

    def fetchall(self):
        if self.fetch_error:
            raise self.fetch_error
        result, self.rows = self.rows, []
        return result

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def cursor(self):
        return self.cursor_value


def test_fetchall_closes_cursor_after_complete_consumption():
    cursor = FakeCursor(rows=[(1,), (2,)])
    result = _Result(cursor)
    assert result.fetchall() == [(1,), (2,)]
    assert cursor.closed


def test_fetchone_closes_cursor_when_exhausted():
    cursor = FakeCursor(rows=[(1,)])
    result = _Result(cursor)
    assert result.fetchone() == (1,)
    assert not cursor.closed
    assert result.fetchone() is None
    assert cursor.closed


@pytest.mark.parametrize("method,args", [("fetchone", ()), ("fetchmany", (10,))])
def test_incremental_fetch_closes_cursor_when_driver_raises(method, args):
    cursor = FakeCursor(fetch_error=RuntimeError("read failed"))
    result = _Result(cursor)
    with pytest.raises(RuntimeError, match="read failed"):
        getattr(result, method)(*args)
    assert cursor.closed


def test_result_context_manager_closes_cursor():
    cursor = FakeCursor(rows=[(1,)])
    with _Result(cursor) as result:
        assert result.fetchone() == (1,)
    assert cursor.closed


def test_execute_closes_cursor_when_driver_raises():
    cursor = FakeCursor(error=RuntimeError("database error"))
    conn = _Conn(FakeConnection(cursor))
    with pytest.raises(RuntimeError, match="database error"):
        conn.execute("SELECT 1")
    assert cursor.closed


def test_executemany_closes_cursor_when_driver_raises():
    cursor = FakeCursor(error=RuntimeError("write error"))
    conn = _Conn(FakeConnection(cursor))
    with pytest.raises(RuntimeError, match="write error"):
        conn.executemany("INSERT INTO t VALUES (%s)", [(1,)])
    assert cursor.closed
