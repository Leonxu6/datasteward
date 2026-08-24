import pytest

from dm.warehouse.store import _Conn


class FailingCursor:
    description = None

    def execute(self, sql, params=None):
        raise RuntimeError("primary database error")

    def close(self):
        raise OSError("cleanup error")


class Connection:
    def cursor(self):
        return FailingCursor()


def test_execute_preserves_primary_driver_error_when_cursor_close_fails():
    conn = _Conn(Connection())
    with pytest.raises(RuntimeError, match="primary database error"):
        conn.execute("SELECT broken")
