"""SQL Server 连接器（用友 U8 的底层库）。"""
from contextlib import contextmanager
from typing import Optional

from dm.config import SRC_MSSQL_DB, SRC_MSSQL_HOST, SRC_MSSQL_PASSWORD, SRC_MSSQL_PORT, SRC_MSSQL_USER
from dm.connect.base import ColumnDef, Connector, DatasetDef, Source, normalize_read_limit
from dm.connect.postgres import _IDENT

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


class SqlServerConnector(Connector):
    source_type = "sqlserver"

    def _connect(self):
        drv, style = _load_driver()
        if drv is None:
            raise RuntimeError("未安装 SQL Server 驱动：pip install -e .[connectors]（pymssql 或 pyodbc）")
        p = self.source.params
        host = p.get("host") or SRC_MSSQL_HOST
        if not host:
            raise RuntimeError("SQL Server 主机未配置（DM_SRC_MSSQL_HOST）——真库到手后设置环境变量")
        pwd = self.source.secret("password", SRC_MSSQL_PASSWORD)
        if style == "pymssql":
            return drv.connect(server=host, port=str(p.get("port", SRC_MSSQL_PORT)), user=p.get("user", SRC_MSSQL_USER), password=pwd, database=p.get("db", SRC_MSSQL_DB), login_timeout=15)
        server = f"{host},{p.get('port', SRC_MSSQL_PORT)}"
        odbc_driver = p.get("odbc_driver") or _DEFAULT_ODBC_DRIVER
        conn_str = (
            f"DRIVER={_odbc_value(odbc_driver)};"
            f"SERVER={_odbc_value(server)};DATABASE={_odbc_value(p.get('db', SRC_MSSQL_DB))};"
            f"UID={_odbc_value(p.get('user', SRC_MSSQL_USER))};PWD={_odbc_value(pwd)}"
        )
        return drv.connect(conn_str, timeout=15)

    def _schema(self, schema: Optional[str] = None) -> str:
        if schema is not None: value = schema
        elif "schema" in self.source.params: value = self.source.params["schema"]
        else: value = "dbo"
        if not isinstance(value, str) or not _IDENT.fullmatch(value): raise ValueError(f"非法 schema: {value}")
        return value

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
        except Exception as e:  # noqa: BLE001
            return False, str(e)

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
        if not _IDENT.fullmatch(name): raise ValueError(f"非法表名: {name}")
        if cursor_col is not None and since is None: raise ValueError("增量读取提供 cursor_col 时必须同时提供 since")
        if since is not None and (not isinstance(cursor_col, str) or not cursor_col.strip()): raise ValueError("增量读取提供 since 时必须同时提供非空 cursor_col")
        schema = self._schema(); limit = normalize_read_limit(limit); ph = "%s" if _load_driver()[1] == "pymssql" else "?"; top = f"TOP ({limit}) " if limit is not None else ""; sql = f"SELECT {top}* FROM [{schema}].[{name}]"; params = []
        if since is not None:
            if not _IDENT.fullmatch(cursor_col): raise ValueError(f"非法游标列: {cursor_col}")
            sql += f" WHERE [{cursor_col}] > {ph}"; params.append(since)
        with self._cursor() as cur: cur.execute(sql, tuple(params) if params else ()); cols = [d[0] for d in cur.description]; rows = [tuple(row) for row in cur.fetchall()]
        return cols, rows

    def capabilities(self) -> dict:
        return {"snapshot": True, "incremental": True, "cdc": False}
