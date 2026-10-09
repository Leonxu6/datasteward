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


def test_main_closes_cursor_and_connection_when_worker_stops(monkeypatch):
    events = []

    class Cursor:
        def execute(self, *args):
            events.append("query")

        def fetchall(self):
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
