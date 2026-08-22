"""共享存储层：StarRocks 数据仓库 + 追加式 JSONL 治理日志。"""
import pymysql

from dm.config import (  # noqa: F401
    LOG_DIR, WH_DB, WH_HOST, WH_PASSWORD, WH_PORT,
    WH_RO_PASSWORD, WH_RO_USER, WH_USER,
)
from dm.warehouse.logio import append_jsonl, read_jsonl
from dm.warehouse.validation import normalize_fetch_size

LOG_DIR.mkdir(parents=True, exist_ok=True)


class _Result:
    """pymysql 游标的 DuckDB 风格薄适配器，完整消费后主动释放游标。"""

    def __init__(self, cur):
        self._cur = cur
        self.description = cur.description
        self._closed = False

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._cur.close()
        except Exception:  # noqa: BLE001
            pass

    def fetchone(self):
        try:
            row = self._cur.fetchone()
        except Exception:
            self.close()
            raise
        if row is None:
            self.close()
        return row

    def fetchmany(self, size):
        size = normalize_fetch_size(size)
        try:
            rows = self._cur.fetchmany(size)
        except Exception:
            self.close()
            raise
        if not rows:
            self.close()
        return rows

    def fetchall(self):
        try:
            return self._cur.fetchall()
        finally:
            self.close()

    def fetchdf(self):
        import pandas as pd

        try:
            rows = self._cur.fetchall()
            cols = [d[0] for d in self.description] if self.description else []
            return pd.DataFrame(list(rows), columns=cols)
        finally:
            self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class _Conn:
    """连接适配器：execute(sql) 返回 _Result；支持 ``with`` 自动关闭。"""

    def __init__(self, conn):
        self._conn = conn

    def _run(self, method: str, sql, params):
        cur = self._conn.cursor()
        try:
            getattr(cur, method)(sql, params)
        except Exception:
            try:
                cur.close()
            finally:
                raise
        return _Result(cur)

    def execute(self, sql, params=None):
        return self._run("execute", sql, params)

    def executemany(self, sql, seq_of_params):
        return self._run("executemany", sql, seq_of_params)

    def commit(self):
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


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
