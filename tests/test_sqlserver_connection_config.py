"""SQL Server 连接字段的前置校验。"""

import pytest

from dm.connect.base import Source
from dm.connect.sqlserver import SqlServerConnector
import dm.connect.sqlserver as sqlserver_module


class _FakePyodbc:
    def __init__(self):
        self.connection_string = None
        self.timeout = None

    def connect(self, connection_string, timeout=0):
        self.connection_string = connection_string
        self.timeout = timeout
        return object()


def test_connect_passes_validated_host_to_pyodbc(monkeypatch):
    driver = _FakePyodbc()
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (driver, "pyodbc"))
    source = Source(
        name="u8",
        source_type="sqlserver",
        params={"host": "sql.internal", "user": "reader", "db": "erp"},
    )
    SqlServerConnector(source)._connect()
    assert "SERVER={sql.internal,1433}" in driver.connection_string


@pytest.mark.parametrize("host", [None, 123, "", " sql.internal", "sql.internal "])
def test_connect_rejects_invalid_host_before_loading_driver(monkeypatch, host):
    monkeypatch.setattr(
        sqlserver_module,
        "_load_driver",
        lambda: (_ for _ in ()).throw(AssertionError("driver should not be loaded")),
    )
    connector = SqlServerConnector(Source(name="u8", source_type="sqlserver", params={"host": host}))
    with pytest.raises(ValueError, match="host"):
        connector._connect()
