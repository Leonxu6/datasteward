import pytest

from dm.app.pages import docs


class _Cursor:
    def __init__(self, rows, *, fail=False):
        self.rows = rows
        self.fail = fail
        self.requested = None
        self.closed = False
        self.executed = None

    def execute(self, sql):
        self.executed = sql

    def fetchmany(self, size):
        self.requested = size
        if self.fail:
            raise RuntimeError("read failed")
        return self.rows[:size]

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


class _Store:
    def __init__(self, connection):
        self.connection = connection
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        return self.connection


def test_registry_rows_reads_one_sentinel_and_reports_truncation():
    cursor = _Cursor(list(range(5)))
    connection = _Connection(cursor)

    rows, truncated = docs._registry_rows(_Store(connection), limit=3)

    assert rows == [0, 1, 2]
    assert truncated is True
    assert cursor.requested == 4
    assert "ORDER BY doc_id" in cursor.executed
    assert cursor.closed is True
    assert connection.closed is True


def test_registry_rows_returns_complete_short_page():
    cursor = _Cursor([("DOC1",), ("DOC2",)])
    connection = _Connection(cursor)

    rows, truncated = docs._registry_rows(_Store(connection), limit=3)

    assert rows == [("DOC1",), ("DOC2",)]
    assert truncated is False


def test_registry_rows_closes_cursor_and_connection_after_fetch_failure():
    cursor = _Cursor([], fail=True)
    connection = _Connection(cursor)

    with pytest.raises(RuntimeError, match="read failed"):
        docs._registry_rows(_Store(connection), limit=3)

    assert cursor.closed is True
    assert connection.closed is True


@pytest.mark.parametrize("limit", [True, 0, -1, 1.5, "10", 1001])
def test_registry_rows_rejects_invalid_limit_before_connect(limit):
    store = _Store(_Connection(_Cursor([])))

    with pytest.raises(ValueError, match="registry limit"):
        docs._registry_rows(store, limit=limit)

    assert store.connect_calls == 0
