"""U8 → StarRocks ODS 批量抽取管道（L2 集成层的"真实源"分支）。

映射：U8 表 → StarRocks `raw_u8__<小写表名>`（ODS 原样落地，主键模型天然 upsert）
     + 本体对象归属（onboard 就绪报告与数据目录用）。
增量：档案类走 dModifyDate 游标、单据类走自增 ID 游标、现存量小表全量刷；
     水位持久化在 logs/u8_watermark.json，重跑只抽新增/变更。
留痕：每表一条审计（category=dataImport，channel=pipeline）——数据进平台也要有账。

真库切换：只改 DM_SRC_MSSQL_*（HOST/PORT/USER/PASSWORD/DB）环境变量；若真库表名/游标列
与仿真不一致，改本文件的 U8_TABLE_MAP 即可，管道逻辑不变。

CLI: dm-u8 full|sync|status [表名...]
"""
import json
import sys
import time
from datetime import date, datetime
from decimal import Decimal

from dm.config import LOG_DIR, WH_DB
from dm.connect.catalog import get_connector
from dm.tools.audit import audit_event
from dm.tools.principal import Principal
from dm.warehouse.store import connect_admin

WATERMARK_FILE = LOG_DIR / "u8_watermark.json"

# U8 表 → ODS/本体映射。cursor=None → 每次全量刷（TRUNCATE+INSERT 语义：小表）
U8_TABLE_MAP = [
    {"u8": "Inventory",       "object": "material",        "cursor": "dModifyDate", "cn": "存货档案"},
    {"u8": "Vendor",          "object": "supplier",        "cursor": "dModifyDate", "cn": "供应商档案"},
    {"u8": "Customer",        "object": "customer",        "cursor": "dModifyDate", "cn": "客户档案"},
    {"u8": "Warehouse",       "object": "warehouse",       "cursor": "dModifyDate", "cn": "仓库档案"},
    {"u8": "Department",      "object": "department",      "cursor": "dModifyDate", "cn": "部门档案"},
    {"u8": "Person",          "object": "employee",        "cursor": "dModifyDate", "cn": "职员档案"},
    {"u8": "ComputationUnit", "object": "unit",            "cursor": "dModifyDate", "cn": "计量单位"},
    {"u8": "CurrentStock",    "object": "inventory",       "cursor": None,          "cn": "现存量"},
    {"u8": "SO_SOMain",       "object": "sales_order",     "cursor": "ID",          "cn": "销售订单主表"},
    {"u8": "SO_SODetails",    "object": "sales_order",     "cursor": "AutoID",      "cn": "销售订单子表"},
    {"u8": "DispatchList",    "object": "delivery_note",   "cursor": "DLID",        "cn": "发货单主表"},
    {"u8": "DispatchLists",   "object": "delivery_note",   "cursor": "AutoID",      "cn": "发货单子表"},
    {"u8": "PO_Pomain",       "object": "purchase_order",  "cursor": "POID",        "cn": "采购订单主表"},
    {"u8": "PO_Podetails",    "object": "purchase_order",  "cursor": "ID",          "cn": "采购订单子表"},
]

_SR_TYPE = {
    "nvarchar": "VARCHAR(512)", "varchar": "VARCHAR(512)", "char": "VARCHAR(255)",
    "nchar": "VARCHAR(255)", "text": "STRING", "ntext": "STRING",
    "int": "INT", "smallint": "INT", "tinyint": "INT", "bigint": "BIGINT",
    "decimal": "DECIMAL(18,4)", "numeric": "DECIMAL(18,4)", "money": "DECIMAL(18,4)",
    "smallmoney": "DECIMAL(18,4)", "float": "DOUBLE", "real": "DOUBLE",
    "datetime": "DATETIME", "datetime2": "DATETIME", "smalldatetime": "DATETIME",
    "date": "DATE", "bit": "BOOLEAN",
}


def ods_name(u8_table: str) -> str:
    return "raw_u8__" + u8_table.lower()


def _load_wm() -> dict:
    if WATERMARK_FILE.exists():
        try:
            return json.loads(WATERMARK_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_wm(wm: dict):
    WATERMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATERMARK_FILE.write_text(json.dumps(wm, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def _sr_ddl(dset, pk_cols: list) -> str:
    """从源自省结果生成 StarRocks 主键模型 DDL（PK 列在前且 NOT NULL）。"""
    cols_pk, cols_rest = [], []
    for c in dset.columns:
        st = _SR_TYPE.get(c.data_type.lower(), "VARCHAR(512)")
        if c.name in pk_cols:
            st = "VARCHAR(255)" if st.startswith("VARCHAR") or st == "STRING" else st
            cols_pk.append(f"`{c.name}` {st} NOT NULL")
        else:
            cols_rest.append(f"`{c.name}` {st} NULL")
    cols_rest.append("`_synced_at` DATETIME NULL")
    key = ", ".join(f"`{c}`" for c in pk_cols)
    body = ",\n  ".join(cols_pk + cols_rest)
    return (f"CREATE TABLE IF NOT EXISTS `{ods_name(dset.name)}` (\n  {body}\n) "
            f"PRIMARY KEY({key}) DISTRIBUTED BY HASH({key}) BUCKETS 1 "
            f'PROPERTIES("replication_num"="1")')


def _norm(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v
    return v


def sync(tables=None, full=False, verbose=True) -> dict:
    """抽取 U8 → StarRocks ODS。tables=None 全部；full=True 忽略水位全量。返回 {表: 抽取行数}。"""
    sid = "U8SYNC" + datetime.now().strftime("%Y%m%d%H%M%S")
    principal = Principal(user="pipeline", role="管理员", purpose="数据同步",
                          session_id=sid, channel="pipeline")
    conn = get_connector("u8_erp")
    dsets = {d.name: d for d in conn.introspect()}
    wm = _load_wm()
    sr = connect_admin(WH_DB)
    report = {}
    for m in U8_TABLE_MAP:
        name = m["u8"]
        if tables and name not in tables:
            continue
        t0 = time.time()
        try:
            dset = dsets.get(name)
            if dset is None:
                report[name] = "源库无此表"
                continue
            pk_cols = dset.primary_key or [dset.columns[0].name]
            sr.execute(_sr_ddl(dset, pk_cols))
            cursor_col = m["cursor"]
            since = None if full else wm.get(name)
            if cursor_col is None:
                # 小表全量刷：先清后灌（主键模型 DELETE 全表 + INSERT）
                cols, rows = conn.read_table(name)
                sr.execute(f"TRUNCATE TABLE `{ods_name(name)}`")
            else:
                cols, rows = conn.read_table(name, cursor_col=cursor_col, since=since)
            if rows:
                now = datetime.now().replace(microsecond=0)
                collist = ", ".join(f"`{c}`" for c in cols) + ", `_synced_at`"
                ph = ", ".join(["%s"] * (len(cols) + 1))
                values = [tuple([_norm(v) for v in r] + [now]) for r in rows]
                for i in range(0, len(values), 500):
                    sr.executemany(f"INSERT INTO `{ods_name(name)}` ({collist}) VALUES ({ph})",
                                   values[i:i + 500])
                if cursor_col:
                    ci = cols.index(cursor_col)
                    mx = max(r[ci] for r in rows)
                    wm[name] = mx.isoformat() if isinstance(mx, (datetime, date)) else mx
            report[name] = len(rows)
            audit_event(principal, "u8_sync",
                        {"table": name, "ods": ods_name(name), "mode": "full" if (full or since is None) else "incr",
                         "since": str(since)}, "", [ods_name(name)], len(rows), t0, True,
                        category="dataImport")
            if verbose:
                print(f"  {name:16} → {ods_name(name):26} +{len(rows)} 行"
                      f"（{'全量' if (full or since is None) else f'增量>{since}'}）")
        except Exception as e:  # noqa: BLE001
            report[name] = f"失败: {e}"
            audit_event(principal, "u8_sync", {"table": name}, "", [ods_name(name)], 0, t0, False,
                        str(e), category="dataImport", decision="deny")
            if verbose:
                print(f"  {name:16} ❌ {e}")
    sr.close()
    _save_wm(wm)
    return report


def status():
    wm = _load_wm()
    print("=== U8 同步水位 ===")
    for m in U8_TABLE_MAP:
        print(f"  {m['u8']:16} cursor={m['cursor'] or '(全量刷)':12} 水位={wm.get(m['u8'], '(未同步)')}")
    try:
        sr = connect_admin(WH_DB)
        rows = sr.execute(
            f"SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema='{WH_DB}' AND table_name LIKE 'raw_u8__%'").fetchall()
        print(f"=== StarRocks ODS：{len(rows)} 张 raw_u8__* ===")
        for (t,) in rows:
            n = sr.execute(f"SELECT COUNT(*) FROM `{t}`").fetchone()[0]
            print(f"  {t:28} {n} 行")
        sr.close()
    except Exception as e:  # noqa: BLE001
        print(f"（StarRocks 不可达：{e}）")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    cmd = args[0] if args else "sync"
    tables = args[1:] or None
    if cmd == "status":
        status()
        return
    ok, msg = get_connector("u8_erp").test_connection()
    if not ok:
        print(f"❌ U8 源不可达：{msg}")
        sys.exit(1)
    rep = sync(tables=tables, full=(cmd == "full"))
    n_ok = sum(1 for v in rep.values() if isinstance(v, int))
    print(f"=== U8 抽取完成：{n_ok}/{len(rep)} 表成功 ===")
    if any(not isinstance(v, int) for v in rep.values()):
        sys.exit(2)


if __name__ == "__main__":
    main()
