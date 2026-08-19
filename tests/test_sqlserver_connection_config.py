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


def test_connect_passes_validated_identity_and_driver_to_pyodbc(monkeypatch):
    driver = _FakePyodbc()
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (driver, "pyodbc"))
    source = Source(
        name="u8",
        source_type="sqlserver",
        params={
            "host": "sql.internal",
            "user": "report_reader",
            "db": "ERP Production",
            "odbc_driver": "ODBC Driver 18 for SQL Server",
        },
    )
    SqlServerConnector(source)._connect()
    assert driver.connection_string.startswith("DRIVER={ODBC Driver 18 for SQL Server};")
    assert "DATABASE={ERP Production}" in driver.connection_string
    assert "UID={report_reader}" in driver.connection_string


@pytest.mark.parametrize(
    ("field", "value"),
    [("user", None), ("user", ""), ("user", " reader"), ("db", 123), ("db", ""), ("db", "erp ")],
)
def test_connect_rejects_invalid_identity_before_loading_driver(monkeypatch, field, value):
    monkeypatch.setattr(
        sqlserver_module,
        "_load_driver",
        lambda: (_ for _ in ()).throw(AssertionError("driver should not be loaded")),
    )
    params = {"host": "sql.internal", "user": "reader", "db": "erp"}
    params[field] = value
    connector = SqlServerConnector(Source(name="u8", source_type="sqlserver", params=params))
    with pytest.raises(ValueError, match=field):
        connector._connect()


@pytest.mark.parametrize("driver_name", [None, 123, "", " ODBC Driver 18", "ODBC Driver 18 "])
def test_pyodbc_rejects_invalid_driver_names_before_connect(monkeypatch, driver_name):
    driver = _FakePyodbc()
    monkeypatch.setattr(sqlserver_module, "_load_driver", lambda: (driver, "pyodbc"))
    source = Source(
        name="u8",
        source_type="sqlserver",
        params={"host": "sql.internal", "user": "reader", "db": "erp", "odbc_driver": driver_name},
    )
    with pytest.raises(ValueError, match="odbc_driver"):
        SqlServerConnector(source)._connect()
    assert driver.connection_string is None
