"""管道健康数据：Flink CDC 作业状态、源/汇对账、复制槽。供 app.py 管道健康视图用。

- flink_jobs(): 经 Flink REST 取作业列表与状态。
- cdc_reconcile(): 逐表对比 Postgres(源) vs StarRocks(汇) 行数，判断是否一致。
- replication_slots(): Postgres 复制槽（CDC 是否在消费 WAL）。
连接：FLINK_REST / SRC_PG_* / WH_*（均经 SSH 隧道，见 config.py）。
"""
from contextlib import closing
import json
import urllib.request

import psycopg2

from dm.config import (FLINK_REST, SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD,
                       SRC_PG_PORT, SRC_PG_USER)
from dm.schema import business_table_names
from dm.warehouse.store import connect_ro


def flink_jobs():
    """Flink 作业概览：[{jid, name, state, duration(ms)}...] 或 {'error':...}。"""
    try:
        with urllib.request.urlopen(f"{FLINK_REST}/jobs/overview", timeout=8) as r:
            return json.load(r).get("jobs", [])
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _pg():
    return psycopg2.connect(host=SRC_PG_HOST, port=SRC_PG_PORT, user=SRC_PG_USER,
                            password=SRC_PG_PASSWORD, dbname=SRC_PG_DB, connect_timeout=8)


def cdc_reconcile():
    """逐表对比 Postgres(源) vs StarRocks(汇) 行数。返回 [{table, source_pg, sink_sr, match}...]。"""
    try:
        out = []
        with closing(_pg()) as pg, closing(pg.cursor()) as pgc, closing(connect_ro()) as sr:
            for t in business_table_names():
                pgc.execute(f'SELECT COUNT(*) FROM "{t}"')
                s = pgc.fetchone()[0]
                d = sr.execute(f"SELECT COUNT(*) FROM `{t}`").fetchone()[0]
                out.append({"table": t, "source_pg": s, "sink_sr": d, "match": s == d})
        return out
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def replication_slots():
    """Postgres 复制槽：[{slot, active}...] 或 {'error':...}。"""
    try:
        with closing(_pg()) as pg, closing(pg.cursor()) as c:
            c.execute("SELECT slot_name, active FROM pg_replication_slots ORDER BY slot_name")
            return [{"slot": r[0], "active": r[1]} for r in c.fetchall()]
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
