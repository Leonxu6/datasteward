import pytest

from dm.eval import run_eval
from dm.eval.schema import EvalCaseError


class Cursor:
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


def test_truth_query_fetches_one_bounded_page_and_closes_resources(monkeypatch):
    cursor = Cursor([(1,), (2,)])
    connection = Connection(cursor)
    monkeypatch.setattr(run_eval, "_MAX_TRUTH_ROWS", 2)
    monkeypatch.setattr(run_eval, "connect_ro", lambda: connection)

    assert run_eval._truth("SELECT value") == [(1,), (2,)]
    assert cursor.fetch_sizes == [3]
    assert cursor.closed is True
    assert connection.closed is True


def test_truth_query_rejects_oversized_results_after_releasing_resources(monkeypatch):
    cursor = Cursor([(1,), (2,), (3,)])
    connection = Connection(cursor)
    monkeypatch.setattr(run_eval, "_MAX_TRUTH_ROWS", 2)
    monkeypatch.setattr(run_eval, "connect_ro", lambda: connection)

    with pytest.raises(EvalCaseError, match="more than 2 rows"):
        run_eval._truth("SELECT value")

    assert cursor.closed is True
    assert connection.closed is True


def test_truth_query_closes_resources_when_fetch_fails(monkeypatch):
    cursor = Cursor([], error=RuntimeError("warehouse unavailable"))
    connection = Connection(cursor)
    monkeypatch.setattr(run_eval, "connect_ro", lambda: connection)

    with pytest.raises(RuntimeError, match="warehouse unavailable"):
        run_eval._truth("SELECT value")

    assert cursor.closed is True
    assert connection.closed is True
