"""对 Postgres 影子源持续制造增删改，演示 CDC 实时同步（S1）。

主要对 inventory 随机 UPDATE（改 qty），偶尔 INSERT/DELETE（仅针对自己插入的 MUT 行）。
避开 eval 关键物料（M0001/M0046/M0050/M0042），不破坏 eval 真值。每步打印操作，Ctrl-C 停止。

用法: python -m dm.sources.mutate [--interval 3]
连接 SRC_PG_*（Windows 经 SSH 隧道 15432→主机 5432）。
"""
import argparse
import random
import sys
import time
from datetime import datetime

import psycopg2

from dm.config import (SRC_PG_DB, SRC_PG_HOST, SRC_PG_PASSWORD, SRC_PG_PORT,
                       SRC_PG_USER)

# eval 关键物料，避开（llm_judge 用例有硬编码 expected）
EVAL_CRITICAL = ("M0001", "M0046", "M0050", "M0042")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=3.0, help="每步间隔秒数")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    conn = psycopg2.connect(host=SRC_PG_HOST, port=SRC_PG_PORT, user=SRC_PG_USER,
                            password=SRC_PG_PASSWORD, dbname=SRC_PG_DB, connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('SELECT id, material_id, warehouse_id, location_id FROM inventory '
                'WHERE material_id NOT IN %s', (EVAL_CRITICAL,))
    safe = cur.fetchall()
    print(f"mutate: {len(safe)} 个可改库存行（已避开 {EVAL_CRITICAL}），间隔 {args.interval}s，Ctrl-C 停止\n")

    seq = 0
    while True:
        seq += 1
        ts = datetime.now().strftime("%H:%M:%S")
        op = random.choices(["update", "insert", "delete"], weights=[7, 2, 1])[0]
        try:
            if op == "update" and safe:
                row = random.choice(safe)
                q = random.randint(1, 999)
                cur.execute("UPDATE inventory SET qty=%s, update_time=now() WHERE id=%s", (q, row[0]))
                print(f"[{ts}] #{seq} UPDATE inventory id={row[0]} ({row[1]}) qty->{q}")
            elif op == "insert" and safe:
                b = random.choice(safe)
                nid = f"MUT{datetime.now().strftime('%H%M%S')}{seq:03d}"
                q = random.randint(1, 500)
                cur.execute("INSERT INTO inventory (id, material_id, warehouse_id, location_id, qty, batch_no, update_time) "
                            "VALUES (%s,%s,%s,%s,%s,%s,now())", (nid, b[1], b[2], b[3], q, "MUTBATCH"))
                print(f"[{ts}] #{seq} INSERT inventory id={nid} ({b[1]}) qty={q}")
            else:  # delete（只删自己插的 MUT 行）
                cur.execute("SELECT id, material_id FROM inventory WHERE id LIKE 'MUT%%' LIMIT 1")
                d = cur.fetchone()
                if d:
                    cur.execute("DELETE FROM inventory WHERE id=%s", (d[0],))
                    print(f"[{ts}] #{seq} DELETE inventory id={d[0]} ({d[1]})")
                else:
                    print(f"[{ts}] #{seq} (无 MUT 行可删，跳过)")
        except Exception as e:  # noqa: BLE001
            print(f"[{ts}] #{seq} ERR {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
