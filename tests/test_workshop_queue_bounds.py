import pytest

from dm.app.pages import workshop


class Cursor:
    description = [("id",), ("value",)]

    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error
        self.fetch_sizes = []

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        if self.error:
            raise self.error
        return self.rows[:size]


class Connection:
    def __init__(self, cursor):
        self.cursor = cursor
        self.closed = False

    def execute(self, sql):
        assert sql == "SELECT queue"
        return self.cursor

    def close(self):
        self.closed = True


def test_queue_query_returns_one_page_and_truncation_signal(monkeypatch):
    cursor = Cursor([(index, f"v{index}") for index in range(5)])
    connection = Connection(cursor)
    monkeypatch.setattr(workshop, "connect_ro", lambda: connection)

    rows, truncated = workshop._q("SELECT queue", limit=3)

    assert rows == [
        {"id": 0, "value": "v0"},
        {"id": 1, "value": "v1"},
        {"id": 2, "value": "v2"},
    ]
    assert truncated is True
    assert cursor.fetch_sizes == [4]
    assert connection.closed is True


def test_queue_query_reports_complete_short_page(monkeypatch):
    cursor = Cursor([(1, "only")])
    connection = Connection(cursor)
    monkeypatch.setattr(workshop, "connect_ro", lambda: connection)

    assert workshop._q("SELECT queue", limit=3) == ([{"id": 1, "value": "only"}], False)
    assert connection.closed is True


def test_queue_query_closes_connection_when_fetch_fails(monkeypatch):
    cursor = Cursor([], error=RuntimeError("read failed"))
    connection = Connection(cursor)
    monkeypatch.setattr(workshop, "connect_ro", lambda: connection)

    with pytest.raises(RuntimeError, match="read failed"):
        workshop._q("SELECT queue", limit=3)

    assert connection.closed is True


@pytest.mark.parametrize("limit", [True, False, 0, -1, 101, 1.5, "15"])
def test_queue_query_rejects_invalid_limits_before_connect(monkeypatch, limit):
    monkeypatch.setattr(
        workshop,
        "connect_ro",
        lambda: (_ for _ in ()).throw(AssertionError("database should not be opened")),
    )

    with pytest.raises(ValueError, match="queue limit"):
        workshop._q("SELECT queue", limit=limit)
