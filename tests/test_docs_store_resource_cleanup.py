import pytest

from dm.docs import store


class Cursor:
    def __init__(self, *, rows=None, fail_on_execute=False):
        self.rows = list(rows or [])
        self.fail_on_execute = fail_on_execute
        self.closed = False
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)
        if self.fail_on_execute:
            raise RuntimeError("driver failure")

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        self.closed = True


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False
        self._autocommit = None
        self.fail_autocommit = False

    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value):
        if self.fail_autocommit:
            raise RuntimeError("cannot configure autocommit")
        self._autocommit = value

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def test_connect_rejects_non_boolean_autocommit(monkeypatch):
    monkeypatch.setattr(store.psycopg2, "connect", lambda **kwargs: pytest.fail("driver should not be called"))
    for value in (1, "true", None):
        with pytest.raises(ValueError):
            store.connect(value)


def test_connect_closes_connection_when_autocommit_configuration_fails(monkeypatch):
    connection = Connection(Cursor())
    connection.fail_autocommit = True
    monkeypatch.setattr(store.psycopg2, "connect", lambda **kwargs: connection)
    with pytest.raises(RuntimeError, match="autocommit"):
        store.connect()
    assert connection.closed


def test_connect_vec_closes_connection_when_registration_fails(monkeypatch):
    cursor = Cursor()
    connection = Connection(cursor)
    monkeypatch.setattr(store, "connect", lambda **kwargs: connection)
    import pgvector.psycopg2
    monkeypatch.setattr(pgvector.psycopg2, "register_vector", lambda conn: (_ for _ in ()).throw(RuntimeError("bad vector")))
    with pytest.raises(RuntimeError):
        store.connect_vec()
    assert connection.closed


def test_init_schema_closes_cursor_and_connection_on_failure(monkeypatch):
    cursor = Cursor(fail_on_execute=True)
    connection = Connection(cursor)
    monkeypatch.setattr(store, "connect", lambda: connection)
    with pytest.raises(RuntimeError):
        store.init_schema()
    assert cursor.closed
    assert connection.closed


def test_counts_closes_resources_and_validates_rows(monkeypatch):
    cursor = Cursor(rows=[(2,), (5,)])
    connection = Connection(cursor)
    monkeypatch.setattr(store, "connect", lambda: connection)
    assert store.counts() == (2, 5)
    assert cursor.closed and connection.closed


@pytest.mark.parametrize("rows", [[], [(1,)], [(True,), (2,)], [(-1,), (2,)], [(1.5,), (2,)]])
def test_counts_rejects_missing_or_invalid_count_rows(monkeypatch, rows):
    cursor = Cursor(rows=rows)
    connection = Connection(cursor)
    monkeypatch.setattr(store, "connect", lambda: connection)
    with pytest.raises(RuntimeError):
        store.counts()
    assert cursor.closed and connection.closed
