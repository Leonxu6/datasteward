"""跨连接器的 read_table(limit=...) 边界测试。"""

import pytest

from dm.connect.base import Source, normalize_read_limit
from dm.connect.postgres import PostgresConnector
from dm.connect.sqlserver import SqlServerConnector
import dm.connect.sqlserver as sqlserver_module


class _FakeCursor:
    def __init__(self):
        self.description = [("id",)]
        self.sql = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return []


class _FakeConnection:
    def __init__(self):
        self.cursor_obj = _FakeCursor()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def _source(source_type: str) -> Source:
    return Source(name="test", source_type=source_type)


def test_normalize_read_limit_accepts_zero_and_rejects_invalid_values():
    assert normalize_read_limit(None) is None
    assert normalize_read_limit(0) == 0
    assert normalize_read_limit(5) == 5

    with pytest.raises(ValueError, match="不能为负数"):
        normalize_read_limit(-1)
    with pytest.raises(ValueError, match="必须是整数"):
        normalize_read_limit(1.5)


def test_postgres_zero_limit_is_sent_to_database(monkeypatch):
    connector = PostgresConnector(_source("postgres"))
    fake = _FakeConnection()
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    columns, rows = connector.read_table("orders", limit=0)

    assert columns == ["id"]
    assert rows == []
    assert fake.cursor_obj.sql == 'SELECT * FROM "orders" LIMIT %s'
    assert fake.cursor_obj.params == [0]


def test_postgres_negative_limit_fails_before_connecting(monkeypatch):
    connector = PostgresConnector(_source("postgres"))
    monkeypatch.setattr(
        connector,
        "_connect",
        lambda: (_ for _ in ()).throw(AssertionError("database should not be contacted")),
    )

    with pytest.raises(ValueError, match="不能为负数"):
        connector.read_table("orders", limit=-1)


def test_sqlserver_zero_limit_uses_top_zero(monkeypatch):
    connector = SqlServerConnector(_source("sqlserver"))
    fake = _FakeConnection()
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (object(), "pymssql"))
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    columns, rows = connector.read_table("orders", limit=0)

    assert columns == ["id"]
    assert rows == []
    assert fake.cursor_obj.sql == "SELECT TOP (0) * FROM [orders]"
    assert fake.cursor_obj.params == ()
    assert fake.closed is True


def test_sqlserver_negative_limit_fails_before_loading_driver(monkeypatch):
    connector = SqlServerConnector(_source("sqlserver"))
    monkeypatch.setattr(
        sqlserver_module,
        "_load_driver",
        lambda: (_ for _ in ()).throw(AssertionError("driver should not be loaded")),
    )

    with pytest.raises(ValueError, match="不能为负数"):
        connector.read_table("orders", limit=-1)
