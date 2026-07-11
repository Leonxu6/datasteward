"""把合成数据灌入 Postgres 影子源（被 Flink CDC 的"假 ERP"）。

S1：在 Postgres 建 19 张 OLTP 表（标准 DDL + 主键 + REPLICA IDENTITY FULL，
便于 CDC 捕获完整 before-image），灌入与 StarRocks 数仓同一批 generate.build_all() 数据。
随后 Flink CDC 从这里全量+增量同步到 StarRocks。

用法: python -m dm.sources.seed_source
连接：dm.config 的 SRC_PG_*（Windows 侧经 SSH 隧道连本地 15432→主机 5432）。
"""
import sys

import psycopg2

from dm.config import (SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD, SRC_PG_PORT,
                       SRC_PG_USER)
from dm.schema import TABLES
from dm.warehouse.generate import build_all

_PGTYPE = {
    "VARCHAR": "VARCHAR(512)",
    "INTEGER": "INTEGER",
    "DOUBLE": "DOUBLE PRECISION",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP",
    "BOOLEAN": "BOOLEAN",
}


def pg_type(typ):
    return _PGTYPE.get(typ.upper(), "VARCHAR(512)")


def ddl(t):
    pk_cols = t["pk"].split("+")
    lines = [f'"{name}" {pg_type(typ)}' for (name, typ, _cn) in t["columns"]]
    lines.append(f'PRIMARY KEY ({", ".join(chr(34) + c + chr(34) for c in pk_cols)})')
    return f'CREATE TABLE "{t["name"]}" (\n  ' + ",\n  ".join(lines) + "\n)"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    conn = psycopg2.connect(host=SRC_PG_HOST, port=SRC_PG_PORT, user=SRC_PG_USER,
                            password=SRC_PG_PASSWORD, dbname=SRC_PG_DB, connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()
    data = build_all()
    for t in TABLES:
        cur.execute(f'DROP TABLE IF EXISTS "{t["name"]}" CASCADE')
        cur.execute(ddl(t))
        # REPLICA IDENTITY FULL：UPDATE/DELETE 时输出完整旧值，CDC 更稳
        cur.execute(f'ALTER TABLE "{t["name"]}" REPLICA IDENTITY FULL')
        rows = data.get(t["name"], [])
        if not rows:
            continue
        cols = [c[0] for c in t["columns"]]
        collist = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(["%s"] * len(cols))
        values = [tuple(r.get(c) for c in cols) for r in rows]
        cur.executemany(f'INSERT INTO "{t["name"]}" ({collist}) VALUES ({ph})', values)

    print(f"=== Postgres 影子源已灌入: {SRC_PG_HOST}:{SRC_PG_PORT}/{SRC_PG_DB} ===")
    total = 0
    for t in TABLES:
        cur.execute(f'SELECT COUNT(*) FROM "{t["name"]}"')
        n = cur.fetchone()[0]
        total += n
        print(f'  {t["name"]:<26} {n:>6} 行')
    print(f"  --- 共 {len(TABLES)} 张表, {total} 行（CDC 源就绪）---")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
