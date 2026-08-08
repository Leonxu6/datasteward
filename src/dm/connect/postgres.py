"""PostgreSQL 连接器：我们的影子源（被 Flink CDC 的"假 ERP"），也可直连真实 PG 客户库。

自省走 information_schema（表/列/类型/主键）——这是"接上客户库就能用"的关键：
不写死表结构，从真实库读元数据自动生成 DatasetDef。CDC 由基建层的 Flink 承担（capabilities.cdc=True）。
"""
import re
from typing import Optional

from dm.config import SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD, SRC_PG_PORT, SRC_PG_USER
from dm.connect.base import ColumnDef, Connector, DatasetDef, Source, normalize_read_limit

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def default_pg_source() -> Source:
    """从 config 构建默认 PG 影子源（凭据只存 env 引用）。"""
    return Source(
        name="pg_shadow", source_type="postgres",
        params={"host": SRC_PG_HOST, "port": SRC_PG_PORT, "user": SRC_PG_USER, "db": SRC_PG_DB},
        credential_env={"password": "DM_SRC_PG_PASSWORD"},
        markings=[], description="PostgreSQL 影子源（Flink CDC 源 / 模拟客户库）",
    )


class PostgresConnector(Connector):
    source_type = "postgres"

    def _connect(self):
        import psycopg
        p = self.source.params
        return psycopg.connect(
            host=p.get("host", SRC_PG_HOST), port=int(p.get("port", SRC_PG_PORT)),
            user=p.get("user", SRC_PG_USER), dbname=p.get("db", SRC_PG_DB),
            password=self.source.secret("password", SRC_PG_PASSWORD),
            connect_timeout=15,
        )

    def test_connection(self) -> tuple:
        try:
            with self._connect() as c, c.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True, "ok"
        except Exception as e:  # noqa: BLE001
            return False, str(e)

    def introspect(self, schema: str = "public") -> list:
        """自省 public schema 下所有基表 → DatasetDef 列表。"""
        out = []
        with self._connect() as c, c.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name", (schema,))
            tables = [r[0] for r in cur.fetchall()]
            # 主键：一次性拉全库
            cur.execute(
                "SELECT tc.table_name, kcu.column_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema "
                "WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_schema=%s", (schema,))
            pk_map: dict = {}
            for tname, col in cur.fetchall():
                pk_map.setdefault(tname, []).append(col)
            for t in tables:
                cur.execute(
                    "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                    "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (schema, t))
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
        sql = f'SELECT * FROM "{name}"'
        params = []
        if cursor_col and since is not None:
            if not _IDENT.match(cursor_col):
                raise ValueError(f"非法游标列: {cursor_col}")
            sql += f' WHERE "{cursor_col}" > %s'   # 对标 Palantir 单调游标 WHERE col > ?
            params.append(since)
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        with self._connect() as c, c.cursor() as cur:
            cur.execute(sql, params or None)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return cols, rows

    def capabilities(self) -> dict:
        return {"snapshot": True, "incremental": True, "cdc": True}
