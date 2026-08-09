"""SQL Server 连接器（用友 U8 的底层库）。

真实客户源。接口与 PostgresConnector 对齐：自省 INFORMATION_SCHEMA + 抽数 + 增量游标。
需可选驱动 `pymssql` 或 `pyodbc`（`pip install -e .[connectors]`）。真库/驱动缺失时
优雅降级：test_connection 返回失败原因，introspect/read_table 抛清晰错误——**接口预留、待真库**。

用友 U8 惯例：表名多为 GBK 语义前缀（如 Inventory/PU_* /SO_*），拿到真实 DDL 后
在源目录/映射层补"U8 表 → 我们对象类型"的映射即可，本连接器逻辑不变。
"""
from contextlib import contextmanager
from typing import Optional

from dm.config import (
    SRC_MSSQL_DB, SRC_MSSQL_HOST, SRC_MSSQL_PASSWORD, SRC_MSSQL_PORT, SRC_MSSQL_USER,
)
from dm.connect.base import ColumnDef, Connector, DatasetDef, Source, normalize_read_limit
from dm.connect.postgres import _IDENT


def default_u8_source() -> Source:
    return Source(
        name="u8_erp", source_type="sqlserver",
        params={"host": SRC_MSSQL_HOST, "port": SRC_MSSQL_PORT,
                "user": SRC_MSSQL_USER, "db": SRC_MSSQL_DB},
        credential_env={"password": "DM_SRC_MSSQL_PASSWORD"},
        markings=[], description="用友 U8 / SQL Server 真实 ERP 源（待真库接入）",
    )


def _load_driver():
    """返回 (module, style)；style ∈ {'pymssql','pyodbc'}。都没有则 (None, None)。"""
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
            return drv.connect(server=host, port=str(p.get("port", SRC_MSSQL_PORT)),
                               user=p.get("user", SRC_MSSQL_USER), password=pwd,
                               database=p.get("db", SRC_MSSQL_DB), login_timeout=15)
        conn_str = (f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{p.get('port', SRC_MSSQL_PORT)};"
                    f"DATABASE={p.get('db', SRC_MSSQL_DB)};UID={p.get('user', SRC_MSSQL_USER)};PWD={pwd}")
        return drv.connect(conn_str, timeout=15)

    @contextmanager
    def _cursor(self):
        """跨 pymssql/pyodbc 的轻量资源管理，异常时也保证释放 cursor/connection。"""
        c = self._connect()
        cur = None
        try:
            cur = c.cursor()
            yield cur
        finally:
            if cur is not None:
                close_cursor = getattr(cur, "close", None)
                if close_cursor is not None:
                    close_cursor()
            c.close()

    def test_connection(self) -> tuple:
        try:
            with self._cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True, "ok"
        except Exception as e:  # noqa: BLE001
            return False, str(e)

    def introspect(self, schema: str = "dbo") -> list:
        out = []
        _, style = _load_driver()
        ph = "%s" if style == "pymssql" else "?"
        with self._cursor() as cur:
            cur.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA={ph} AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
                (schema,),
            )
            tables = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT tc.TABLE_NAME, kcu.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
                "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
                "ON tc.CONSTRAINT_NAME=kcu.CONSTRAINT_NAME "
                "AND tc.CONSTRAINT_SCHEMA=kcu.CONSTRAINT_SCHEMA "
                f"WHERE tc.CONSTRAINT_TYPE='PRIMARY KEY' AND tc.TABLE_SCHEMA={ph}",
                (schema,),
            )
            pk_map: dict = {}
            for tname, col in cur.fetchall():
                pk_map.setdefault(tname, []).append(col)
            for t in tables:
                cur.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS "
                    f"WHERE TABLE_SCHEMA={ph} AND TABLE_NAME={ph} ORDER BY ORDINAL_POSITION",
                    (schema, t),
                )
                pks = set(pk_map.get(t, []))
                cols = [ColumnDef(name=cn, data_type=dt, nullable=(nl == "YES"),
                                  is_primary_key=(cn in pks)) for cn, dt, nl in cur.fetchall()]
                out.append(DatasetDef(name=t, columns=cols, primary_key=pk_map.get(t, [])))
        return out

    def read_table(self, name: str, limit: Optional[int] = None,
                   cursor_col: Optional[str] = None, since=None) -> tuple:
        if not _IDENT.match(name):
            raise ValueError(f"非法表名: {name}")
        limit = normalize_read_limit(limit)
        ph = "%s" if _load_driver()[1] == "pymssql" else "?"
        top = f"TOP ({limit}) " if limit is not None else ""
        sql = f"SELECT {top}* FROM [{name}]"
        params = []
        if cursor_col and since is not None:
            if not _IDENT.match(cursor_col):
                raise ValueError(f"非法游标列: {cursor_col}")
            sql += f" WHERE [{cursor_col}] > {ph}"
            params.append(since)
        with self._cursor() as cur:
            cur.execute(sql, tuple(params) if params else ())
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return cols, rows

    def capabilities(self) -> dict:
        # U8/SQL Server 支持 CDC，但我们 PoC 阶段先批量+增量；CDC 待真库评估
        return {"snapshot": True, "incremental": True, "cdc": False}
