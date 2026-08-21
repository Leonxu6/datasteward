"""共享存储层：StarRocks 数据仓库 + 追加式 JSONL 治理日志。"""
import pymysql

from dm.config import (  # noqa: F401  (LOG_DIR re-exported for consumers)
    LOG_DIR, WH_DB, WH_HOST, WH_PASSWORD, WH_PORT,
    WH_RO_PASSWORD, WH_RO_USER, WH_USER,
)
from dm.warehouse.logio import append_jsonl, read_jsonl

LOG_DIR.mkdir(parents=True, exist_ok=True)


class _Result:
    """包一层 pymysql 游标，暴露 DuckDB 风格取数接口。"""

    def __init__(self, cur):
        self._cur = cur
        self.description = cur.description

    def fetchone(self):
        return self._cur.fetchone()

    def fetchmany(self, size):
        return self._cur.fetchmany(size)

    def fetchall(self):
        return self._cur.fetchall()

    def fetchdf(self):
        import pandas as pd
        rows = self._cur.fetchall()
        cols = [d[0] for d in self._cur.description] if self._cur.description else []
        return pd.DataFrame(list(rows), columns=cols)


class _Conn:
    """连接适配器：execute(sql) 返回 _Result；close() 关闭底层连接。"""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return _Result(cur)

    def executemany(self, sql, seq_of_params):
        cur = self._conn.cursor()
        cur.executemany(sql, seq_of_params)
        return _Result(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass


def _connect(user, password, database, autocommit=True):
    return pymysql.connect(
        host=WH_HOST,
        port=WH_PORT,
        user=user,
        password=password,
        database=database,
        autocommit=autocommit,
        charset="utf8mb4",
        connect_timeout=15,
        read_timeout=120,
        write_timeout=120,
    )


def connect_ro():
    """只读查询连接（智能体 / 浏览 / eval 标准答案）。"""
    return _Conn(_connect(WH_RO_USER, WH_RO_PASSWORD, WH_DB))


def connect_admin(database=None):
    """管理连接（建库 / 建表 / 灌数）。"""
    return _Conn(_connect(WH_USER, WH_PASSWORD, database))


def append_log(name, record: dict):
    """向 logs/<name>.jsonl 原子追加一条 JSON 对象记录。"""
    append_jsonl(LOG_DIR, name, record)


def read_log(name) -> list:
    """读取 logs/<name>.jsonl 中所有有效 JSON 对象。"""
    return read_jsonl(LOG_DIR, name)
