"""Quoted SQL Server identifier behavior."""

from dm.connect.base import Source
from dm.connect.sqlserver import SqlServerConnector
import dm.connect.sqlserver as sqlserver_module


class _Cursor:
    def __init__(self):
        self.description = [("id",)]
        self.sql = None
        self.params = None
        self.closed = False

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return [(1,)]

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.cursor_obj = _Cursor()
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def test_sqlserver_read_safely_quotes_complex_identifiers(monkeypatch):
    connector = SqlServerConnector(
        Source(name="u8", source_type="sqlserver", params={"schema": "ERP Data"})
    )
    connection = _Connection()
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (object(), "pyodbc"))
    monkeypatch.setattr(connector, "_connect", lambda: connection)

    columns, rows = connector.read_table("Order ] Items", cursor_col="updated at", since=10)

    assert columns == ["id"]
    assert rows == [(1,)]
    assert connection.cursor_obj.sql == "SELECT * FROM [ERP Data].[Order ]] Items] WHERE [updated at] > ?"
    assert connection.cursor_obj.params == (10,)
    assert connection.cursor_obj.closed is True
    assert connection.closed is True


def test_sqlserver_schema_accepts_quoted_identifier_text():
    connector = SqlServerConnector(Source(name="u8", source_type="sqlserver"))

    assert connector._schema("ERP Production") == "ERP Production"
    assert connector._schema("erp-prod") == "erp-prod"
    assert connector._schema("库存") == "库存"
