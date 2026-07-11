"""共享存储层（S0 起：数据仓库为 StarRocks，MySQL 协议）。

- 数据仓库：StarRocks（MySQL 协议）。所有消费方（MCP 查询 / Streamlit 浏览 / eval 标准答案）
  只跑 SELECT；load.py 是唯一建库/灌数者。连接参数取自 dm.config 的 WH_*
  （开发机默认经 SSH 隧道连本地 127.0.0.1:9030）。
- logs/*.jsonl：审计 / 任务链 / eval 留痕，**追加式** JSONL，跨进程并发安全，与数仓解耦
  （管理平台可在 agent 运行时实时读日志）。

connect_ro() 返回一个**薄适配器**，对外暴露与原 DuckDB 一致的接口
（execute(sql) → 结果对象，支持 fetchone / fetchmany(n) / fetchall / fetchdf / description；
 以及 close()），因此 mcp_server / app / eval 等消费方无需改动取数代码。
"""
import json
from datetime import date, datetime

import pymysql

from dm.config import (  # noqa: F401  (LOG_DIR re-exported for consumers)
    LOG_DIR, WH_DB, WH_HOST, WH_PASSWORD, WH_PORT,
    WH_RO_PASSWORD, WH_RO_USER, WH_USER,
)

LOG_DIR.mkdir(parents=True, exist_ok=True)


# ----------------- DuckDB 风格连接适配器（底层 StarRocks / MySQL 协议） -----------------
class _Result:
    """包一层 pymysql 游标，暴露 DuckDB 风格取数接口。"""

    def __init__(self, cur):
        self._cur = cur
        self.description = cur.description  # d[0] 为列名，兼容原 mcp_server 用法

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
        host=WH_HOST, port=WH_PORT, user=user, password=password,
        database=database, autocommit=autocommit, charset="utf8mb4",
        connect_timeout=15, read_timeout=120, write_timeout=120,
    )


def connect_ro():
    """只读查询连接（智能体 / 浏览 / eval 标准答案）。

    语义只读：消费方只跑 SELECT；mcp_server 另有 SQL 白名单兜底。
    建好 dm_ro 只读用户后，WH_RO_USER 切过去即得"连接级只读"双保险。
    """
    return _Conn(_connect(WH_RO_USER, WH_RO_PASSWORD, WH_DB))


def connect_admin(database=None):
    """管理连接（建库 / 建表 / 灌数）。database=None 时不选库（用于 CREATE DATABASE）。"""
    return _Conn(_connect(WH_USER, WH_PASSWORD, database))


# ----------------- 追加式 JSONL 留痕（审计 / 任务链 / eval，与数仓解耦） -----------------
def _json_default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return str(o)


def append_log(name, record: dict):
    """向 logs/<name>.jsonl 追加一条记录。"""
    p = LOG_DIR / f"{name}.jsonl"
    line = json.dumps(record, ensure_ascii=False, default=_json_default)
    with open(p, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_log(name) -> list:
    """读取 logs/<name>.jsonl 为 list[dict]。"""
    p = LOG_DIR / f"{name}.jsonl"
    if not p.exists():
        return []
    out = []
    with open(p, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    return out
