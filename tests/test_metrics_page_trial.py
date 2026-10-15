import pytest

from dm.app.pages import metrics_page


class Cursor:
    description = [("metric",), ("value",)]

    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error
        self.fetch_sizes = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.closed = True

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        if self.error:
            raise self.error
        return self.rows[:size]


class Connection:
    def __init__(self, cursor):
        self.cursor = cursor
        self.executed = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.closed = True

    def execute(self, sql):
        self.executed.append(sql)
        return self.cursor


def test_metric_trial_fetches_one_bounded_page_and_closes_resources(monkeypatch):
    cursor = Cursor([("orders", 42), ("revenue", 99)])
    connection = Connection(cursor)
    monkeypatch.setattr(metrics_page, "connect_ro", lambda: connection)

    cols, rows = metrics_page._run_metric_trial("SELECT metric, value", row_limit=2)

    assert cols == ["metric", "value"]
    assert rows == [("orders", 42), ("revenue", 99)]
    assert cursor.fetch_sizes == [2]
    assert cursor.closed is True
    assert connection.closed is True


def test_metric_trial_closes_resources_when_fetch_fails(monkeypatch):
    cursor = Cursor([], error=RuntimeError("database password leaked"))
    connection = Connection(cursor)
    monkeypatch.setattr(metrics_page, "connect_ro", lambda: connection)

    with pytest.raises(RuntimeError, match="password leaked"):
        metrics_page._run_metric_trial("SELECT metric")

    assert cursor.closed is True
    assert connection.closed is True


@pytest.mark.parametrize("row_limit", [True, False, 0, -1, 201, 1.5, "10"])
def test_metric_trial_rejects_invalid_limits_before_connect(monkeypatch, row_limit):
    monkeypatch.setattr(
        metrics_page,
        "connect_ro",
        lambda: (_ for _ in ()).throw(AssertionError("database should not be opened")),
    )

    with pytest.raises(ValueError, match="trial row limit"):
        metrics_page._run_metric_trial("SELECT metric", row_limit=row_limit)
