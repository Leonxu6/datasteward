"""管道健康数据：Flink CDC 作业状态、源/汇对账、复制槽。供 app.py 管道健康视图用。

- flink_jobs(): 经 Flink REST 取作业列表与状态。
- cdc_reconcile(): 逐表对比 Postgres(源) vs StarRocks(汇) 行数，判断是否一致。
- replication_slots(): Postgres 复制槽（CDC 是否在消费 WAL）。
连接：FLINK_REST / SRC_PG_* / WH_*（均经 SSH 隧道，见 config.py）。
"""
from contextlib import closing
import json
import re
import urllib.request

import psycopg2

from dm.config import (FLINK_REST, SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD,
                       SRC_PG_PORT, SRC_PG_USER)
from dm.schema import business_table_names
from dm.warehouse.store import connect_ro

_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_MAX_RECONCILE_TABLES = 100


def _flink_job_list(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("Flink overview must be an object")
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs):
        raise ValueError("Flink jobs must be a list of objects")
    return jobs


def _row_count(row: object) -> int:
    if not isinstance(row, (tuple, list)) or len(row) != 1:
        raise ValueError("count query must return one column")
    value = row[0]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("count query must return a non-negative integer")
    return value


def _business_tables(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("business table registry must be a list or tuple")
    if len(value) > _MAX_RECONCILE_TABLES:
        raise ValueError("business table registry is too large")
    tables: list[str] = []
    seen: set[str] = set()
    for table in value:
        if not isinstance(table, str) or not _TABLE_NAME.fullmatch(table):
            raise ValueError("business table names must be safe SQL identifiers")
        if table in seen:
            raise ValueError("business table registry contains duplicate names")
        seen.add(table)
        tables.append(table)
    return tables


def _replication_slot_row(row: object) -> dict[str, object]:
    if not isinstance(row, (tuple, list)) or len(row) != 2:
        raise ValueError("replication slot query returned a malformed row")
    slot, active = row
    if not isinstance(slot, str) or not slot or slot != slot.strip():
        raise ValueError("replication slot name must be clean non-empty text")
    if not isinstance(active, bool):
        raise ValueError("replication slot active state must be boolean")
    return {"slot": slot, "active": active}


def flink_jobs():
    """Flink 作业概览：[{jid, name, state, duration(ms)}...] 或 {'error':...}。"""
    try:
        with urllib.request.urlopen(f"{FLINK_REST}/jobs/overview", timeout=8) as r:
            return _flink_job_list(json.load(r))
    except Exception:  # noqa: BLE001
        return {"error": "Flink job query failed"}


def _pg():
    return psycopg2.connect(host=SRC_PG_HOST, port=SRC_PG_PORT, user=SRC_PG_USER,
                            password=SRC_PG_PASSWORD, dbname=SRC_PG_DB, connect_timeout=8)


def cdc_reconcile():
    """逐表对比 Postgres(源) vs StarRocks(汇) 行数。返回 [{table, source_pg, sink_sr, match}...]。"""
    try:
        tables = _business_tables(business_table_names())
        out = []
        with closing(_pg()) as pg, closing(pg.cursor()) as pgc, closing(connect_ro()) as sr:
            for table in tables:
                pgc.execute(f'SELECT COUNT(*) FROM "{table}"')
                source_count = _row_count(pgc.fetchone())
                sink_count = _row_count(sr.execute(f"SELECT COUNT(*) FROM `{table}`").fetchone())
                out.append({
                    "table": table,
                    "source_pg": source_count,
                    "sink_sr": sink_count,
                    "match": source_count == sink_count,
                })
        return out
    except Exception:  # noqa: BLE001
        return {"error": "source/sink reconciliation failed"}


def replication_slots():
    """Postgres 复制槽：[{slot, active}...] 或 {'error':...}。"""
    try:
        with closing(_pg()) as pg, closing(pg.cursor()) as c:
            c.execute("SELECT slot_name, active FROM pg_replication_slots ORDER BY slot_name")
            return [_replication_slot_row(row) for row in c.fetchall()]
    except Exception:  # noqa: BLE001
        return {"error": "replication slot query failed"}
