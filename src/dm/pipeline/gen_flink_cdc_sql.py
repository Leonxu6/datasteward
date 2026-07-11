"""从 schema.py 生成 Flink SQL：postgres-cdc 源 → starrocks 汇，全量+增量同步。

每张业务表生成一个 src_<t>(postgres-cdc) + sink_<t>(starrocks)，最后用一个
STATEMENT SET 把所有 INSERT 合成一个 Flink 作业。容器内主机名直连（同 compose 网络）。

用法（默认全 19 表，可传表名只生成子集，便于单表打通）:
  python -m dm.pipeline.gen_flink_cdc_sql                 > cdc_all.sql
  python -m dm.pipeline.gen_flink_cdc_sql inventory       > cdc_inv.sql
提交（见 infra/submit-cdc.sh）:
  docker compose cp infra/cdc_all.sql flink-jobmanager:/tmp/
  docker compose exec flink-jobmanager /opt/flink/bin/sql-client.sh -f /tmp/cdc_all.sql
"""
import os
import sys

from dm.config import SRC_PG_DB, SRC_PG_PASSWORD, SRC_PG_USER, WH_DB
from dm.schema import TABLES

_FT = {"VARCHAR": "STRING", "INTEGER": "INT", "DOUBLE": "DOUBLE",
       "DATE": "DATE", "TIMESTAMP": "TIMESTAMP(3)", "BOOLEAN": "BOOLEAN"}

# 容器内主机名 = compose 服务名（Flink 在 compose 网络内直连源/汇），可用 env 覆盖；
# 库名/凭据与 dm.config 同源（生成时不带环境变量即得到仓库默认值）。
PG = {"host": os.environ.get("DM_CDC_PG_HOST", "postgres"), "port": "5432",
      "db": SRC_PG_DB, "user": SRC_PG_USER, "pw": SRC_PG_PASSWORD}
# load-url 用 FE(8030)：compose 已把 BE 的 priority_networks/注册改成容器 IP，
# 故 FE 的 Stream Load 重定向指向 BE 容器 IP:8040，Flink 跨容器可达。
_SR_HOST = os.environ.get("DM_CDC_SR_HOST", "starrocks")
SR = {"jdbc": f"jdbc:mysql://{_SR_HOST}:9030", "load": f"{_SR_HOST}:8030",
      "db": WH_DB, "user": "root", "pw": ""}


def ft(typ):
    return _FT.get(typ.upper(), "STRING")


def _cols(t):
    pk = t["pk"].split("+")
    lines = [f'  `{n}` {ft(ty)}' for (n, ty, _c) in t["columns"]]
    lines.append("  PRIMARY KEY (" + ", ".join(f"`{c}`" for c in pk) + ") NOT ENFORCED")
    return ",\n".join(lines)


def src_ddl(t):
    return (
        f'CREATE TABLE `src_{t["name"]}` (\n{_cols(t)}\n) WITH (\n'
        f"  'connector' = 'postgres-cdc',\n"
        f"  'hostname' = '{PG['host']}',\n  'port' = '{PG['port']}',\n"
        f"  'username' = '{PG['user']}',\n  'password' = '{PG['pw']}',\n"
        f"  'database-name' = '{PG['db']}',\n  'schema-name' = 'public',\n"
        f"  'table-name' = '{t['name']}',\n"
        f"  'slot.name' = 'flink_{t['name']}',\n"
        f"  'decoding.plugin.name' = 'pgoutput',\n"
        f"  'scan.incremental.snapshot.enabled' = 'true'\n);")


def sink_ddl(t):
    return (
        f'CREATE TABLE `sink_{t["name"]}` (\n{_cols(t)}\n) WITH (\n'
        f"  'connector' = 'starrocks',\n"
        f"  'jdbc-url' = '{SR['jdbc']}',\n  'load-url' = '{SR['load']}',\n"
        f"  'database-name' = '{SR['db']}',\n  'table-name' = '{t['name']}',\n"
        f"  'username' = '{SR['user']}',\n  'password' = '{SR['pw']}',\n"
        f"  'sink.semantic' = 'at-least-once',\n"
        f"  'sink.buffer-flush.interval-ms' = '3000'\n);")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    names = sys.argv[1:] or None
    tabs = [t for t in TABLES if (names is None or t["name"] in names)]
    out = ["SET 'execution.checkpointing.interval' = '5s';",
           "SET 'pipeline.name' = 'dm-cdc-pg-to-starrocks';", ""]
    for t in tabs:
        out += [src_ddl(t), sink_ddl(t), ""]
    out.append("EXECUTE STATEMENT SET\nBEGIN")
    for t in tabs:
        out.append(f'INSERT INTO `sink_{t["name"]}` SELECT * FROM `src_{t["name"]}`;')
    out.append("END;")
    print("\n".join(out))


if __name__ == "__main__":
    main()
