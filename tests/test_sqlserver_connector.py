"""SqlServerConnector 的纯单元测试，不需要真实 SQL Server 驱动或数据库。"""

import pytest

from dm.connect.base import Source
from dm.connect.sqlserver import SqlServerConnector, default_u8_source
import dm.connect.sqlserver as sqlserver_module


class _IntrospectionCursor:
    def __init__(self):
        self.calls = []
        self._responses = iter(
            [
                [("orders",)],
                [("orders", "tenant_id"), ("orders", "order_id")],
                [
                    ("tenant_id", "int", "NO"),
                    ("order_id", "int", "NO"),
                    ("name", "varchar", "YES"),
                ],
            ]
        )
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchall(self):
        return next(self._responses)

    def close(self):
        self.closed = True


class _IntrospectionConnection:
    def __init__(self, cursor=None):
        self.cursor_obj = cursor or _IntrospectionCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


class _FailingCursor:
    def __init__(self):
        self.closed = False

    def execute(self, sql, params=()):
        raise RuntimeError("query failed")

    def close(self):
        self.closed = True


class _CloseFailingCursor:
    def __init__(self):
        self.description = [("id",)]

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return [(1,)]

    def close(self):
        raise RuntimeError("cursor close failed")


class _DriverRow(list):
    """模拟 pyodbc.Row：可迭代，但不是 tuple。"""


class _ReadCursor:
    def __init__(self):
        self.description = [("id",), ("name",)]
        self.closed = False

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return [_DriverRow([1, "alpha"]), _DriverRow([2, "beta"])]

    def close(self):
        self.closed = True


def test_default_u8_source_pins_dbo_schema():
    assert default_u8_source().params["schema"] == "dbo"


def test_introspect_uses_configured_schema_and_preserves_composite_pk_order(monkeypatch):
    connector = SqlServerConnector(
        Source(name="u8", source_type="sqlserver", params={"schema": "erp"})
    )
    fake = _IntrospectionConnection()
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (object(), "pymssql"))
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    datasets = connector.introspect()

    assert len(datasets) == 1
    assert datasets[0].name == "orders"
    assert datasets[0].primary_key == ["tenant_id", "order_id"]
    assert datasets[0].col_names() == ["tenant_id", "order_id", "name"]
    assert [c.is_primary_key for c in datasets[0].columns] == [True, True, False]
    assert datasets[0].columns[2].nullable is True

    table_sql, table_params = fake.cursor_obj.calls[0]
    pk_sql, pk_params = fake.cursor_obj.calls[1]
    column_sql, column_params = fake.cursor_obj.calls[2]

    assert "TABLE_SCHEMA=%s" in table_sql
    assert table_params == ("erp",)
    assert "tc.TABLE_SCHEMA=%s" in pk_sql
    assert "tc.CONSTRAINT_SCHEMA=kcu.CONSTRAINT_SCHEMA" in pk_sql
    assert "ORDER BY tc.TABLE_NAME, kcu.ORDINAL_POSITION" in pk_sql
    assert pk_params == ("erp",)
    assert "TABLE_SCHEMA=%s AND TABLE_NAME=%s" in column_sql
    assert column_params == ("erp", "orders")
    assert fake.cursor_obj.closed is True
    assert fake.closed is True


def test_read_table_qualifies_configured_schema(monkeypatch):
    connector = SqlServerConnector(
        Source(name="u8", source_type="sqlserver", params={"schema": "erp"})
    )
    cursor = _ReadCursor()
    fake = _IntrospectionConnection(cursor=cursor)
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (object(), "pyodbc"))
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    connector.read_table("orders", cursor_col="id", since=10)

    assert cursor.sql == "SELECT * FROM [erp].[orders] WHERE [id] > ?"
    assert cursor.params == (10,)


def test_invalid_configured_schema_fails_before_loading_driver(monkeypatch):
    connector = SqlServerConnector(
        Source(name="u8", source_type="sqlserver", params={"schema": "erp;drop"})
    )
    monkeypatch.setattr(
        sqlserver_module,
        "_load_driver",
        lambda: (_ for _ in ()).throw(AssertionError("driver should not be loaded")),
    )

    with pytest.raises(ValueError, match="非法 schema"):
        connector.read_table("orders")


def test_read_table_closes_cursor_and_connection_when_query_fails(monkeypatch):
    connector = SqlServerConnector(Source(name="u8", source_type="sqlserver"))
    cursor = _FailingCursor()
    fake = _IntrospectionConnection(cursor=cursor)
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (object(), "pymssql"))
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    with pytest.raises(RuntimeError, match="query failed"):
        connector.read_table("orders")

    assert cursor.closed is True
    assert fake.closed is True


def test_test_connection_closes_resources_on_failure(monkeypatch):
    connector = SqlServerConnector(Source(name="u8", source_type="sqlserver"))
    cursor = _FailingCursor()
    fake = _IntrospectionConnection(cursor=cursor)
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    ok, message = connector.test_connection()

    assert ok is False
    assert "query failed" in message
    assert cursor.closed is True
    assert fake.closed is True


def test_connection_closes_even_if_cursor_close_raises(monkeypatch):
    connector = SqlServerConnector(Source(name="u8", source_type="sqlserver"))
    cursor = _CloseFailingCursor()
    fake = _IntrospectionConnection(cursor=cursor)
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (object(), "pymssql"))
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    with pytest.raises(RuntimeError, match="cursor close failed"):
        connector.read_table("orders")

    assert fake.closed is True


def test_read_table_normalizes_driver_rows_to_tuples(monkeypatch):
    connector = SqlServerConnector(Source(name="u8", source_type="sqlserver"))
    cursor = _ReadCursor()
    fake = _IntrospectionConnection(cursor=cursor)
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (object(), "pyodbc"))
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    columns, rows = connector.read_table("orders")

    assert columns == ["id", "name"]
    assert rows == [(1, "alpha"), (2, "beta")]
    assert all(type(row) is tuple for row in rows)
    assert cursor.closed is True
    assert fake.closed is True
