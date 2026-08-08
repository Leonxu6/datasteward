"""SqlServerConnector 的纯单元测试，不需要真实 SQL Server 驱动或数据库。"""

from dm.connect.base import Source
from dm.connect.sqlserver import SqlServerConnector
import dm.connect.sqlserver as sqlserver_module


class _IntrospectionCursor:
    def __init__(self):
        self.calls = []
        self._responses = iter(
            [
                [("orders",)],
                [("orders", "id")],
                [("id", "int", "NO"), ("name", "varchar", "YES")],
            ]
        )

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchall(self):
        return next(self._responses)


class _IntrospectionConnection:
    def __init__(self):
        self.cursor_obj = _IntrospectionCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def test_introspect_scopes_tables_primary_keys_and_columns_to_schema(monkeypatch):
    connector = SqlServerConnector(Source(name="u8", source_type="sqlserver"))
    fake = _IntrospectionConnection()
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (object(), "pymssql"))
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    datasets = connector.introspect(schema="erp")

    assert len(datasets) == 1
    assert datasets[0].name == "orders"
    assert datasets[0].primary_key == ["id"]
    assert datasets[0].col_names() == ["id", "name"]
    assert datasets[0].columns[0].is_primary_key is True
    assert datasets[0].columns[1].nullable is True

    table_sql, table_params = fake.cursor_obj.calls[0]
    pk_sql, pk_params = fake.cursor_obj.calls[1]
    column_sql, column_params = fake.cursor_obj.calls[2]

    assert "TABLE_SCHEMA=%s" in table_sql
    assert table_params == ("erp",)
    assert "tc.TABLE_SCHEMA=%s" in pk_sql
    assert "tc.CONSTRAINT_SCHEMA=kcu.CONSTRAINT_SCHEMA" in pk_sql
    assert pk_params == ("erp",)
    assert "TABLE_SCHEMA=%s AND TABLE_NAME=%s" in column_sql
    assert column_params == ("erp", "orders")
    assert fake.closed is True
