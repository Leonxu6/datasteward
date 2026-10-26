import pytest

from dm.warehouse import store
from dm.warehouse.store import _Result


class Cursor:
    description = (("id",),)

    def __init__(self, rows=None):
        self.calls = []
        self.closed = False
        self.rows = [] if rows is None else rows

    def fetchmany(self, size):
        self.calls.append(size)
        return self.rows

    def close(self):
        self.closed = True


def test_fetchmany_normalizes_valid_size_and_closes_on_exhaustion():
    cursor = Cursor()
    result = _Result(cursor)
    assert result.fetchmany(5) == []
    assert cursor.calls == [5]
    assert cursor.closed


def test_fetchmany_closes_after_partial_final_batch():
    cursor = Cursor([(1,), (2,)])
    result = _Result(cursor)
    assert result.fetchmany(5) == [(1,), (2,)]
    assert cursor.calls == [5]
    assert cursor.closed


def test_fetchmany_keeps_cursor_open_for_full_batch():
    cursor = Cursor([(1,), (2,)])
    result = _Result(cursor)
    assert result.fetchmany(2) == [(1,), (2,)]
    assert not cursor.closed


@pytest.mark.parametrize("size", [True, 0, -1, 1.5, "10", None])
def test_fetchmany_rejects_invalid_size_before_driver_call(size):
    cursor = Cursor()
    result = _Result(cursor)
    with pytest.raises(ValueError):
        result.fetchmany(size)
    assert cursor.calls == []
    assert not cursor.closed


def test_fetchall_enforces_a_driver_level_row_budget(monkeypatch):
    monkeypatch.setattr(store, "_MAX_FETCHALL_ROWS", 2)
    cursor = Cursor([(1,), (2,), (3,)])

    with pytest.raises(RuntimeError, match="2-row fetchall limit"):
        _Result(cursor).fetchall()

    assert cursor.calls == [3]
    assert cursor.closed


def test_fetchdf_uses_the_same_row_budget(monkeypatch):
    monkeypatch.setattr(store, "_MAX_FETCHALL_ROWS", 2)
    cursor = Cursor([(1,), (2,), (3,)])

    with pytest.raises(RuntimeError, match="2-row fetchall limit"):
        _Result(cursor).fetchdf()

    assert cursor.calls == [3]
    assert cursor.closed


def test_fetchall_rejects_malformed_driver_batches(monkeypatch):
    monkeypatch.setattr(store, "_MAX_FETCHALL_ROWS", 2)
    cursor = Cursor(None)
    cursor.rows = None

    with pytest.raises(TypeError, match="invalid row batch"):
        _Result(cursor).fetchall()

    assert cursor.calls == [3]
    assert cursor.closed
