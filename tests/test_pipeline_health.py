from __future__ import annotations

from unittest.mock import patch

import dm.pipeline.health as health


class _Cursor:
    def __init__(self, rows=None, *, fail_execute=False):
        self.rows = list(rows or [])
        self.fail_execute = fail_execute
        self.closed = False
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if self.fail_execute:
            raise RuntimeError("database unavailable")
        return self

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows

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


class _Warehouse:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def execute(self, query):
        return self._cursor.execute(query)

    def close(self):
        self.closed = True


def test_cdc_reconcile_closes_connections_and_cursors_after_success():
    pg_cursor = _Cursor([(2,)])
    pg = _Connection(pg_cursor)
    sr_cursor = _Cursor([(2,)])
    sr = _Warehouse(sr_cursor)
    with (
        patch.object(health, "_pg", return_value=pg),
        patch.object(health, "connect_ro", return_value=sr),
        patch.object(health, "business_table_names", return_value=["inventory"]),
    ):
        assert health.cdc_reconcile() == [
            {"table": "inventory", "source_pg": 2, "sink_sr": 2, "match": True}
        ]
    assert pg_cursor.closed is True
    assert pg.closed is True
    assert sr.closed is True


def test_cdc_reconcile_closes_resources_when_query_fails():
    pg_cursor = _Cursor(fail_execute=True)
    pg = _Connection(pg_cursor)
    sr = _Warehouse(_Cursor([(2,)]))
    with (
        patch.object(health, "_pg", return_value=pg),
        patch.object(health, "connect_ro", return_value=sr),
        patch.object(health, "business_table_names", return_value=["inventory"]),
    ):
        result = health.cdc_reconcile()
    assert "error" in result
    assert pg_cursor.closed is True
    assert pg.closed is True
    assert sr.closed is True


def test_replication_slots_closes_cursor_and_connection():
    cursor = _Cursor([("slot_a", True)])
    pg = _Connection(cursor)
    with patch.object(health, "_pg", return_value=pg):
        assert health.replication_slots() == [{"slot": "slot_a", "active": True}]
    assert cursor.closed is True
    assert pg.closed is True
