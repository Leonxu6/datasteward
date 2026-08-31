from unittest.mock import patch

import dm.pipeline.health as health


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False

    def execute(self, query):
        return None

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


def test_replication_slots_reject_malformed_rows_and_close_resources():
    invalid = (None, (), ("slot",), ("", True), (" slot", True), ("slot", 1), ("slot", True, "extra"))
    for row in invalid:
        cursor = _Cursor([row])
        connection = _Connection(cursor)
        with patch.object(health, "_pg", return_value=connection):
            assert health.replication_slots() == {"error": "replication slot query failed"}
        assert cursor.closed is True
        assert connection.closed is True


def test_replication_slots_preserve_valid_rows():
    cursor = _Cursor([("slot_a", True), ("slot_b", False)])
    connection = _Connection(cursor)
    with patch.object(health, "_pg", return_value=connection):
        assert health.replication_slots() == [
            {"slot": "slot_a", "active": True},
            {"slot": "slot_b", "active": False},
        ]
