"""CDC demo workers validate pacing and release database resources."""

import argparse
import sys

import pytest

from dm.sources import mutate


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "-inf", "not-a-number"])
def test_positive_interval_rejects_nonpositive_or_nonfinite_values(value):
    with pytest.raises(argparse.ArgumentTypeError, match="finite positive"):
        mutate._positive_interval(value)


@pytest.mark.parametrize("value, expected", [("0.1", 0.1), ("3", 3.0)])
def test_positive_interval_accepts_finite_positive_values(value, expected):
    assert mutate._positive_interval(value) == expected


def test_load_mutation_candidates_uses_deterministic_bounded_query():
    class Cursor:
        def __init__(self):
            self.query = None
            self.params = None

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchmany(self, size):
            assert size == 3
            return [("row-1", "M1000", "W1", "L1")]

    cursor = Cursor()

    rows = mutate._load_mutation_candidates(cursor, limit=2)

    assert rows == [("row-1", "M1000", "W1", "L1")]
    assert "ORDER BY id LIMIT %s" in cursor.query
    assert cursor.params == (mutate.EVAL_CRITICAL, 3)


def test_load_mutation_candidates_rejects_an_oversize_dataset():
    class Cursor:
        def execute(self, query, params):
            pass

        def fetchmany(self, size):
            assert size == 3
            return [("row-1",), ("row-2",), ("row-3",)]

    with pytest.raises(RuntimeError, match="2-row safety limit"):
        mutate._load_mutation_candidates(Cursor(), limit=2)


@pytest.mark.parametrize("limit", [True, 0, -1, 1.5])
def test_load_mutation_candidates_rejects_invalid_limits(limit):
    class Cursor:
        def execute(self, *args):
            raise AssertionError("invalid limits must fail before querying")

    with pytest.raises(ValueError, match="positive integer"):
        mutate._load_mutation_candidates(Cursor(), limit=limit)


def test_main_closes_cursor_and_connection_when_worker_stops(monkeypatch):
    events = []

    class Cursor:
        def execute(self, *args):
            events.append("query")

        def fetchmany(self, size):
            return []

        def close(self):
            events.append("cursor-close")

    class Connection:
        autocommit = False

        def cursor(self):
            return Cursor()

        def close(self):
            events.append("connection-close")

    monkeypatch.setattr(mutate.psycopg2, "connect", lambda **kwargs: Connection())
    monkeypatch.setattr(mutate, "_run_mutations", lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    monkeypatch.setattr(sys, "argv", ["dm.sources.mutate", "--interval", "1"])

    with pytest.raises(KeyboardInterrupt):
        mutate.main()

    assert events[-2:] == ["cursor-close", "connection-close"]


def test_main_closes_connection_when_cursor_setup_fails(monkeypatch):
    closed = []

    class Connection:
        autocommit = False

        def cursor(self):
            raise RuntimeError("cursor unavailable")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(mutate.psycopg2, "connect", lambda **kwargs: Connection())
    monkeypatch.setattr(sys, "argv", ["dm.sources.mutate"])

    with pytest.raises(RuntimeError, match="cursor unavailable"):
        mutate.main()

    assert closed == [True]
