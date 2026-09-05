"""U8 → StarRocks ODS 批量抽取管道。

映射：U8 表 → StarRocks `raw_u8__<小写表名>`；增量水位持久化在
`logs/u8_watermark.json`。状态文件采用原子替换，显式表名和游标列在写入
StarRocks 前完成校验，避免半成功同步留下不可恢复的水位状态。

CLI: dm-u8 full|sync|status [表名...]
"""
import sys
import time
from datetime import date, datetime
from decimal import Decimal

from dm.config import LOG_DIR, WH_DB
from dm.connect.catalog import get_connector
from dm.connect.sync_state import (
    atomic_write_json,
    load_json_mapping,
    max_non_null,
    serialize_watermark,
    validate_requested_names,
)
from dm.tools.audit import audit_event
from dm.tools.principal import Principal
from dm.warehouse.store import connect_admin

WATERMARK_FILE = LOG_DIR / "u8_watermark.json"

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


def _safe_failure(exc: BaseException) -> str:
    """Return useful failure classification without exposing backend exception text."""
    return exc.__class__.__name__


def ods_name(u8_table: str) -> str:
    return "raw_u8__" + u8_table.lower()


def _load_wm() -> dict:
    return load_json_mapping(WATERMARK_FILE)


def _save_wm(wm: dict):
    atomic_write_json(WATERMARK_FILE, wm)


def _sr_ddl(dset, pk_cols: list) -> str:
    """从源自省结果生成 StarRocks 主键模型 DDL。"""
    if not dset.columns:
        raise ValueError(f"{dset.name} 没有可同步列")
    if not pk_cols:
        raise ValueError(f"{dset.name} 缺少主键列")
    known = {column.name for column in dset.columns}
    missing = [name for name in pk_cols if name not in known]
    if missing:
        raise ValueError(f"{dset.name} 主键列不在自省结果中: {missing}")

    cols_pk, cols_rest = [], []
    for column in dset.columns:
        starrocks_type = _SR_TYPE.get(column.data_type.lower(), "VARCHAR(512)")
        if column.name in pk_cols:
            if starrocks_type.startswith("VARCHAR") or starrocks_type == "STRING":
                starrocks_type = "VARCHAR(255)"
            cols_pk.append(f"`{column.name}` {starrocks_type} NOT NULL")
        else:
            cols_rest.append(f"`{column.name}` {starrocks_type} NULL")
    cols_rest.append("`_synced_at` DATETIME NULL")
    key = ", ".join(f"`{column}`" for column in pk_cols)
    body = ",\n  ".join(cols_pk + cols_rest)
    return (
        f"CREATE TABLE IF NOT EXISTS `{ods_name(dset.name)}` (\n  {body}\n) "
        f"PRIMARY KEY({key}) DISTRIBUTED BY HASH({key}) BUCKETS 1 "
        f'PROPERTIES("replication_num"="1")'
    )


def _norm(value):
    # pymysql/StarRocks accepts Decimal directly; preserving it avoids float precision loss.
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (datetime, date)):
        return value
    return value


def sync(tables=None, full=False, verbose=True) -> dict:
    """抽取 U8 → StarRocks ODS。返回 {表: 抽取行数或错误描述}。"""
    mapped_names = [mapping["u8"] for mapping in U8_TABLE_MAP]
    requested = validate_requested_names(tables, mapped_names)
    selected = set(requested) if requested is not None else None

    sid = "U8SYNC" + datetime.now().strftime("%Y%m%d%H%M%S")
    principal = Principal(
        user="pipeline", role="管理员", purpose="数据同步", session_id=sid, channel="pipeline"
    )
    conn = get_connector("u8_erp")
    dsets = {dataset.name: dataset for dataset in conn.introspect()}
    wm = _load_wm()
    report = {}
    sr = connect_admin(WH_DB)
    try:
        for mapping in U8_TABLE_MAP:
            name = mapping["u8"]
            if selected is not None and name not in selected:
                continue
            t0 = time.time()
            try:
                dset = dsets.get(name)
                if dset is None:
                    report[name] = "源库无此表"
                    continue
                if not dset.columns:
                    raise ValueError("源表没有可同步列")
                pk_cols = dset.primary_key or [dset.columns[0].name]
                sr.execute(_sr_ddl(dset, pk_cols))

                cursor_col = mapping["cursor"]
                since = None if full else wm.get(name)
                if cursor_col is None:
                    cols, rows = conn.read_table(name)
                    sr.execute(f"TRUNCATE TABLE `{ods_name(name)}`")
                    cursor_max = None
                else:
                    cols, rows = conn.read_table(name, cursor_col=cursor_col, since=since)
                    if cursor_col not in cols:
                        raise ValueError(f"增量游标列 {cursor_col!r} 不在读取结果中")
                    cursor_index = cols.index(cursor_col)
                    cursor_max = max_non_null(row[cursor_index] for row in rows)

                if rows:
                    now = datetime.now().replace(microsecond=0)
                    collist = ", ".join(f"`{column}`" for column in cols) + ", `_synced_at`"
                    placeholders = ", ".join(["%s"] * (len(cols) + 1))
                    values = [tuple([_norm(value) for value in row] + [now]) for row in rows]
                    for index in range(0, len(values), 500):
                        sr.executemany(
                            f"INSERT INTO `{ods_name(name)}` ({collist}) VALUES ({placeholders})",
                            values[index:index + 500],
                        )
                    if cursor_col and cursor_max is not None:
                        wm[name] = serialize_watermark(cursor_max)

                report[name] = len(rows)
                audit_event(
                    principal,
                    "u8_sync",
                    {
                        "table": name,
                        "ods": ods_name(name),
                        "mode": "full" if (full or since is None) else "incr",
                        "since": str(since),
                    },
                    "",
                    [ods_name(name)],
                    len(rows),
                    t0,
                    True,
                    category="dataImport",
                )
                if verbose:
                    mode = "全量" if (full or since is None) else f"增量>{since}"
                    print(f"  {name:16} → {ods_name(name):26} +{len(rows)} 行（{mode}）")
            except Exception as exc:  # noqa: BLE001
                failure = _safe_failure(exc)
                report[name] = f"失败: {failure}"
                audit_event(
                    principal,
                    "u8_sync",
                    {"table": name},
                    "",
                    [ods_name(name)],
                    0,
                    t0,
                    False,
                    failure,
                    category="dataImport",
                    decision="deny",
                )
                if verbose:
                    print(f"  {name:16} ❌ 同步失败（{failure}）")
    finally:
        sr.close()

    _save_wm(wm)
    return report


def status():
    wm = _load_wm()
    print("=== U8 同步水位 ===")
    for mapping in U8_TABLE_MAP:
        print(
            f"  {mapping['u8']:16} cursor={mapping['cursor'] or '(全量刷)':12} "
            f"水位={wm.get(mapping['u8'], '(未同步)')}"
        )
    sr = None
    try:
        sr = connect_admin(WH_DB)
        rows = sr.execute(
            f"SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema='{WH_DB}' AND table_name LIKE 'raw_u8__%'"
        ).fetchall()
        print(f"=== StarRocks ODS：{len(rows)} 张 raw_u8__* ===")
        for (table,) in rows:
            count = sr.execute(f"SELECT COUNT(*) FROM `{table}`").fetchone()[0]
            print(f"  {table:28} {count} 行")
    except Exception as exc:  # noqa: BLE001
        print(f"（StarRocks 不可达：{_safe_failure(exc)}）")
    finally:
        if sr is not None:
            sr.close()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    cmd = args[0] if args else "sync"
    if cmd not in {"sync", "full", "status"}:
        raise SystemExit(f"未知命令 {cmd!r}；可选 sync / full / status")
    tables = args[1:] or None
    if cmd == "status":
        status()
        return
    try:
        ok, _message = get_connector("u8_erp").test_connection()
    except Exception as exc:  # noqa: BLE001
        print(f"❌ U8 源不可达（{_safe_failure(exc)}）")
        raise SystemExit(1) from None
    if not ok:
        print("❌ U8 源不可达")
        raise SystemExit(1)
    report = sync(tables=tables, full=(cmd == "full"))
    succeeded = sum(1 for value in report.values() if isinstance(value, int))
    print(f"=== U8 抽取完成：{succeeded}/{len(report)} 表成功 ===")
    if any(not isinstance(value, int) for value in report.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
