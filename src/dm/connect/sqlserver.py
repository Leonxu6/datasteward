"""SQL Server 连接器（用友 U8 的底层库）。"""
from contextlib import contextmanager
from typing import Optional

from dm.config import SRC_MSSQL_DB, SRC_MSSQL_HOST, SRC_MSSQL_PASSWORD, SRC_MSSQL_PORT, SRC_MSSQL_USER
from dm.connect.base import ColumnDef, Connector, DatasetDef, Source, normalize_port, normalize_read_limit, normalize_timeout
from dm.connect.validation import normalize_identifier, normalize_required_text

_DEFAULT_ODBC_DRIVER = "ODBC Driver 17 for SQL Server"


def default_u8_source() -> Source:
    return Source(name="u8_erp", source_type="sqlserver", params={"host": SRC_MSSQL_HOST, "port": SRC_MSSQL_PORT, "user": SRC_MSSQL_USER, "db": SRC_MSSQL_DB, "schema": "dbo"}, credential_env={"password": "DM_SRC_MSSQL_PASSWORD"}, markings=[], description="用友 U8 / SQL Server 真实 ERP 源（待真库接入）")


def _load_driver():
    try:
        import pymssql
        return pymssql, "pymssql"
    except ImportError:
        pass
    try:
        import pyodbc
        return pyodbc, "pyodbc"
    except ImportError:
        return None, None


def _odbc_value(value) -> str:
    return "{" + str(value).replace("}", "}}") + "}"


def _quote_ident(value, *, field_name: str) -> str:
    """按 SQL Server 方括号规则安全引用 schema/table/column 标识符。"""
    value = normalize_identifier(value, field_name=field_name)
    return "[" + value.replace("]", "]]" ) + "]"


def _connection_error(exc: BaseException) -> str:
    """Keep health checks useful without exposing driver/credential details."""
    return f"SQL Server connection failed ({exc.__class__.__name__})"


class SqlServerConnector(Connector):
    source_type = "sqlserver"

    def _connect(self):
        p = self.source.params
        port = normalize_port(p.get("port"), default=SRC_MSSQL_PORT)
        timeout = normalize_timeout(p.get("connect_timeout"), default=15)
        host = normalize_required_text(p["host"] if "host" in p else SRC_MSSQL_HOST, field_name="host")
        user = normalize_required_text(p["user"] if "user" in p else SRC_MSSQL_USER, field_name="user")
        database = normalize_required_text(p["db"] if "db" in p else SRC_MSSQL_DB, field_name="db")
        drv, style = _load_driver()
        if drv is None:
            raise RuntimeError("未安装 SQL Server 驱动：pip install -e .[connectors]（pymssql 或 pyodbc）")
        pwd = self.source.secret("password", SRC_MSSQL_PASSWORD)
        if style == "pymssql":
            return drv.connect(server=host, port=str(port), user=user, password=pwd, database=database, login_timeout=timeout)
        server = f"{host},{port}"
        odbc_driver = normalize_required_text(
            p["odbc_driver"] if "odbc_driver" in p else _DEFAULT_ODBC_DRIVER,
            field_name="odbc_driver",
        )
        conn_str = (
            f"DRIVER={_odbc_value(odbc_driver)};"
            f"SERVER={_odbc_value(server)};DATABASE={_odbc_value(database)};"
            f"UID={_odbc_value(user)};PWD={_odbc_value(pwd)}"
        )
        return drv.connect(conn_str, timeout=timeout)

    def _schema(self, schema: Optional[str] = None) -> str:
        if schema is not None:
            value = schema
        elif "schema" in self.source.params:
            value = self.source.params["schema"]
        else:
            value = "dbo"
        try:
            return normalize_identifier(value, field_name="schema")
        except ValueError as exc:
            raise ValueError(f"非法 schema: {value!r}") from exc

    @contextmanager
    def _cursor(self):
        c = self._connect(); cur = None
        try:
            cur = c.cursor(); yield cur
        finally:
            try:
                if cur is not None:
                    close_cursor = getattr(cur, "close", None)
                    if close_cursor is not None: close_cursor()
            finally: c.close()

    def test_connection(self) -> tuple:
        try:
            with self._cursor() as cur: cur.execute("SELECT 1"); cur.fetchone()
            return True, "ok"
        except Exception as exc:  # noqa: BLE001
            return False, _connection_error(exc)

    def introspect(self, schema: Optional[str] = None) -> list:
        schema = self._schema(schema); out = []
        _, style = _load_driver(); ph = "%s" if style == "pymssql" else "?"
        with self._cursor() as cur:
            cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES " f"WHERE TABLE_SCHEMA={ph} AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME", (schema,)); tables = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT tc.TABLE_NAME, kcu.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu ON tc.CONSTRAINT_NAME=kcu.CONSTRAINT_NAME AND tc.CONSTRAINT_SCHEMA=kcu.CONSTRAINT_SCHEMA " f"WHERE tc.CONSTRAINT_TYPE='PRIMARY KEY' AND tc.TABLE_SCHEMA={ph} ORDER BY tc.TABLE_NAME, kcu.ORDINAL_POSITION", (schema,))
            pk_map: dict = {}
            for tname, col in cur.fetchall(): pk_map.setdefault(tname, []).append(col)
            for t in tables:
                cur.execute("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS " f"WHERE TABLE_SCHEMA={ph} AND TABLE_NAME={ph} ORDER BY ORDINAL_POSITION", (schema, t)); pks = set(pk_map.get(t, [])); cols = [ColumnDef(name=cn, data_type=dt, nullable=(nl == "YES"), is_primary_key=(cn in pks)) for cn, dt, nl in cur.fetchall()]; out.append(DatasetDef(name=t, columns=cols, primary_key=pk_map.get(t, [])))
        return out

    def read_table(self, name: str, limit: Optional[int] = None, cursor_col: Optional[str] = None, since=None) -> tuple:
        try:
            table_sql = _quote_ident(name, field_name="table")
        except ValueError as exc:
            raise ValueError(f"非法表名: {name!r}") from exc
        if cursor_col is not None and since is None: raise ValueError("增量读取提供 cursor_col 时必须同时提供 since")
        if since is not None and (not isinstance(cursor_col, str) or not cursor_col.strip()): raise ValueError("增量读取提供 since 时必须同时提供非空 cursor_col")
        schema = self._schema(); limit = normalize_read_limit(limit); ph = "%s" if _load_driver()[1] == "pymssql" else "?"; top = f"TOP ({limit}) " if limit is not None else ""; sql = f"SELECT {top}* FROM {_quote_ident(schema, field_name='schema')}.{table_sql}"; params = []
        if since is not None:
            try:
                cursor_sql = _quote_ident(cursor_col, field_name="cursor_col")
            except ValueError as exc:
                raise ValueError(f"非法游标列: {cursor_col!r}") from exc
            sql += f" WHERE {cursor_sql} > {ph}"; params.append(since)
        with self._cursor() as cur: cur.execute(sql, tuple(params) if params else ()); cols = [d[0] for d in cur.description]; rows = [tuple(row) for row in cur.fetchall()]
        return cols, rows

    def capabilities(self) -> dict:
        return {"snapshot": True, "incremental": True, "cdc": False}
