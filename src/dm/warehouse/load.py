"""建库 + 灌数到 StarRocks 数据仓库（幂等：每次重建 19 张业务表）。

S0：数仓由 DuckDB 切换为 **StarRocks**（MySQL 协议，**主键模型**，为 S1 CDC upsert 预留）。
连接参数取自 dm.config 的 WH_*（开发机经 SSH 隧道连 127.0.0.1:9030）。
用法: dm-load（或 python -m dm.warehouse.load）

注：审计/任务链/Eval 留痕仍走 logs/*.jsonl（见 store.py），不建到数仓。
"""
import sys

from dm.config import WH_DB, WH_HOST, WH_PORT
from dm.schema import TABLES
from dm.warehouse.generate import build_all
from dm.warehouse.store import connect_admin

# 通用 SQL 类型 → StarRocks 类型
_TYPE = {
    "INTEGER": "INT",
    "DOUBLE": "DOUBLE",
    "DATE": "DATE",
    "TIMESTAMP": "DATETIME",
    "BOOLEAN": "BOOLEAN",
}


def sr_type(typ, is_pk):
    typ = typ.upper()
    if typ == "VARCHAR":
        return "VARCHAR(255)" if is_pk else "VARCHAR(512)"
    return _TYPE.get(typ, "VARCHAR(512)")


def ddl(t):
    """StarRocks 主键模型建表。主键列在最前、NOT NULL（schema 已保证 pk 列在首位）。"""
    pk_cols = t["pk"].split("+")
    lines = []
    for (name, typ, cn) in t["columns"]:
        is_pk = name in pk_cols
        nn = "NOT NULL" if is_pk else "NULL"
        cn_esc = cn.replace('"', "")
        lines.append(f'  `{name}` {sr_type(typ, is_pk)} {nn} COMMENT "{cn_esc}"')
    cols = ",\n".join(lines)
    pk = ", ".join(f"`{c}`" for c in pk_cols)
    return (
        f'CREATE TABLE `{t["name"]}` (\n{cols}\n) '
        f"PRIMARY KEY ({pk}) "
        f"DISTRIBUTED BY HASH({pk}) BUCKETS 1 "
        f'PROPERTIES ("replication_num" = "1")'
    )


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # 1) 建库（不选库的管理连接）
    admin = connect_admin(database=None)
    admin.execute(f"CREATE DATABASE IF NOT EXISTS `{WH_DB}`")
    admin.close()

    # 2) 重建 19 张业务表并灌数
    con = connect_admin(database=WH_DB)
    try:
        data = build_all()
        for t in TABLES:
            con.execute(f'DROP TABLE IF EXISTS `{t["name"]}`')
            con.execute(ddl(t))
            rows = data.get(t["name"], [])
            if not rows:
                continue
            cols = [c[0] for c in t["columns"]]
            collist = ", ".join(f"`{c}`" for c in cols)
            ph = ", ".join(["%s"] * len(cols))
            values = [[r.get(c) for c in cols] for r in rows]
            con.executemany(
                f'INSERT INTO `{t["name"]}` ({collist}) VALUES ({ph})', values)

        # 3) 报告
        print(f"=== StarRocks 数据仓库已构建: {WH_HOST}:{WH_PORT} / db={WH_DB} ===")
        total = 0
        for t in TABLES:
            n = con.execute(f'SELECT COUNT(*) FROM `{t["name"]}`').fetchone()[0]
            total += n
            print(f'  {t["name"]:<26} {t["cn"]:<16} {n:>6} 行')
        print(f"  --- 共 {len(TABLES)} 张业务表, {total} 行 ---")
        print("  （审计/任务链/Eval 留痕用 logs/*.jsonl 追加式存储）")
    finally:
        con.close()


if __name__ == "__main__":
    main()
