"""仿真用友 U8 源：在 SQL Server（azure-sql-edge 容器）里建 UFDATA_999_2026 + 14 张 U8 风格表并灌样例数据。

目的：真库不可达时，用**同协议（TDS）+ 真实 U8 表名/列名风格**联调整条接入链路
（dm-connect test/onboard → dm-u8 full/sync → StarRocks ODS → dbt）。真库到手改
DM_SRC_MSSQL_* 四个环境变量即切，管道零改动。

样例数据 ID 一律带 U8 前缀（U8M####/U8V###/U8C###...），与合成 19 表的 M####/S### 体系
错开——绝不污染 eval 真值。数据确定性生成（固定种子），可重复重建。

用法: python -m dm.sources.seed_u8_sim
连接：dm.config 的 SRC_MSSQL_*（仿真容器默认 127.0.0.1:11433 / 容器网 sim-u8:1433）。
azure-sql-edge 镜像不带 sqlcmd——一切初始化必须像本脚本这样经 TDS 客户端外灌。
"""
import random
import sys
from datetime import date, datetime, timedelta

from dm.config import SRC_MSSQL_DB, SRC_MSSQL_HOST, SRC_MSSQL_PASSWORD, SRC_MSSQL_PORT, SRC_MSSQL_USER

ANCHOR = date(2026, 6, 25)   # 与合成数据 TODAY 锚点同一天（dm/warehouse/generate.py）
DB = SRC_MSSQL_DB or "UFDATA_999_2026"

# U8 真实风格 DDL（子集列；identity 主键单据 + 编码主键档案）
TABLES_DDL = {
    "Inventory": """CREATE TABLE Inventory (
        cInvCode NVARCHAR(60) NOT NULL PRIMARY KEY,  -- 存货编码
        cInvName NVARCHAR(255) NOT NULL,             -- 存货名称
        cInvStd NVARCHAR(255) NULL,                  -- 规格型号
        cInvCCode NVARCHAR(60) NULL,                 -- 存货分类编码
        cComUnitCode NVARCHAR(60) NULL,              -- 主计量单位编码
        iSafeNum DECIMAL(18,4) NULL,                 -- 安全库存
        dModifyDate DATETIME NOT NULL)""",
    "Vendor": """CREATE TABLE Vendor (
        cVenCode NVARCHAR(60) NOT NULL PRIMARY KEY,
        cVenName NVARCHAR(255) NOT NULL,
        cVenAbbName NVARCHAR(255) NULL,
        cVenPerson NVARCHAR(60) NULL,                -- 联系人（PII）
        cVenPhone NVARCHAR(60) NULL,                 -- 电话（PII）
        dModifyDate DATETIME NOT NULL)""",
    "Customer": """CREATE TABLE Customer (
        cCusCode NVARCHAR(60) NOT NULL PRIMARY KEY,
        cCusName NVARCHAR(255) NOT NULL,
        cCusAbbName NVARCHAR(255) NULL,
        cCusPerson NVARCHAR(60) NULL,
        cCusPhone NVARCHAR(60) NULL,
        iCusCreLine DECIMAL(18,2) NULL,              -- 信用额度（FIN）
        dModifyDate DATETIME NOT NULL)""",
    "Warehouse": """CREATE TABLE Warehouse (
        cWhCode NVARCHAR(60) NOT NULL PRIMARY KEY,
        cWhName NVARCHAR(255) NOT NULL,
        cWhAddress NVARCHAR(255) NULL,
        dModifyDate DATETIME NOT NULL)""",
    "Department": """CREATE TABLE Department (
        cDepCode NVARCHAR(60) NOT NULL PRIMARY KEY,
        cDepName NVARCHAR(255) NOT NULL,
        dModifyDate DATETIME NOT NULL)""",
    "Person": """CREATE TABLE Person (
        cPersonCode NVARCHAR(60) NOT NULL PRIMARY KEY,
        cPersonName NVARCHAR(60) NOT NULL,
        cDepCode NVARCHAR(60) NULL,
        cPersonPhone NVARCHAR(60) NULL,
        dModifyDate DATETIME NOT NULL)""",
    "ComputationUnit": """CREATE TABLE ComputationUnit (
        cComunitCode NVARCHAR(60) NOT NULL PRIMARY KEY,
        cComunitName NVARCHAR(60) NOT NULL,
        dModifyDate DATETIME NOT NULL)""",
    "CurrentStock": """CREATE TABLE CurrentStock (
        AutoId INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        cWhCode NVARCHAR(60) NOT NULL,
        cInvCode NVARCHAR(60) NOT NULL,
        iQuantity DECIMAL(18,4) NOT NULL)""",
    "SO_SOMain": """CREATE TABLE SO_SOMain (
        ID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        cSOCode NVARCHAR(60) NOT NULL,               -- 销售订单号
        cCusCode NVARCHAR(60) NOT NULL,
        cDepCode NVARCHAR(60) NULL,
        cPersonCode NVARCHAR(60) NULL,
        dDate DATETIME NOT NULL,
        cState INT NOT NULL DEFAULT 1)""",
    "SO_SODetails": """CREATE TABLE SO_SODetails (
        AutoID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ID INT NOT NULL,                             -- → SO_SOMain.ID
        cInvCode NVARCHAR(60) NOT NULL,
        iQuantity DECIMAL(18,4) NOT NULL,
        iTaxUnitPrice DECIMAL(18,4) NULL,            -- 含税单价（FIN）
        dPreDate DATETIME NULL)""",
    "DispatchList": """CREATE TABLE DispatchList (
        DLID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        cDLCode NVARCHAR(60) NOT NULL,               -- 发货单号
        cCusCode NVARCHAR(60) NOT NULL,
        cSOCode NVARCHAR(60) NULL,
        dDate DATETIME NOT NULL)""",
    "DispatchLists": """CREATE TABLE DispatchLists (
        AutoID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        DLID INT NOT NULL,                           -- → DispatchList.DLID
        cInvCode NVARCHAR(60) NOT NULL,
        iQuantity DECIMAL(18,4) NOT NULL,
        iTaxUnitPrice DECIMAL(18,4) NULL)""",
    "PO_Pomain": """CREATE TABLE PO_Pomain (
        POID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        cPOID NVARCHAR(60) NOT NULL,                 -- 采购订单号
        cVenCode NVARCHAR(60) NOT NULL,
        dPODate DATETIME NOT NULL,
        cState INT NOT NULL DEFAULT 1)""",
    "PO_Podetails": """CREATE TABLE PO_Podetails (
        ID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        POID INT NOT NULL,                           -- → PO_Pomain.POID
        cInvCode NVARCHAR(60) NOT NULL,
        iQuantity DECIMAL(18,4) NOT NULL,
        iUnitPrice DECIMAL(18,4) NULL,               -- 无税单价（FIN）
        dArriveDate DATETIME NULL)""",
}


def _connect(database=None):
    import pymssql
    return pymssql.connect(server=SRC_MSSQL_HOST or "127.0.0.1", port=str(SRC_MSSQL_PORT),
                           user=SRC_MSSQL_USER or "sa", password=SRC_MSSQL_PASSWORD,
                           database=database or "master", login_timeout=20, autocommit=True)


def _dt(d: date, hour=10):
    return datetime(d.year, d.month, d.day, hour, 0, 0)


def _gen_rows():
    """确定性样例数据（固定种子）。返回 {table: (cols, rows)}。"""
    rnd = random.Random(20260625)
    units = [("U8U01", "件"), ("U8U02", "千克"), ("U8U03", "米"), ("U8U04", "套"), ("U8U05", "箱")]
    whs = [("U8W01", "原材料一库", "厂区A栋"), ("U8W02", "半成品库", "厂区B栋"), ("U8W03", "成品库", "厂区C栋")]
    deps = [("U8D01", "销售部"), ("U8D02", "采购部"), ("U8D03", "生产部"), ("U8D04", "仓储部")]
    persons = [(f"U8P{i:03d}", f"员工{i:03d}", rnd.choice(deps)[0], f"137{rnd.randint(10000000, 99999999)}")
               for i in range(1, 11)]
    mats = []
    for i in range(1, 31):
        mats.append((f"U8M{i:04d}", f"仿真物料-{i:04d}", f"φ{rnd.randint(5, 80)}×{rnd.randint(10, 500)}mm",
                     f"U8MC{rnd.randint(1, 5):02d}", rnd.choice(units)[0], rnd.choice([0, 10, 20, 50, 100]),
                     _dt(ANCHOR - timedelta(days=rnd.randint(5, 90)))))
    vens = [(f"U8V{i:03d}", f"仿真供应商{i:03d}有限公司", f"仿供{i:03d}", f"联系人{i:03d}",
             f"138{rnd.randint(10000000, 99999999)}", _dt(ANCHOR - timedelta(days=rnd.randint(5, 90))))
            for i in range(1, 9)]
    cuss = [(f"U8C{i:03d}", f"仿真客户{i:03d}制造有限公司", f"仿客{i:03d}", f"客户联系人{i:03d}",
             f"139{rnd.randint(10000000, 99999999)}", rnd.choice([50000, 100000, 200000, 500000]),
             _dt(ANCHOR - timedelta(days=rnd.randint(5, 90))))
            for i in range(1, 11)]
    stock = []
    for m in mats:
        for wh, _, _ in rnd.sample(whs, rnd.randint(1, 2)):
            stock.append((wh, m[0], rnd.randint(0, 300)))
    so_main, so_det = [], []
    for i in range(1, 13):
        so_main.append((f"U8SO{i:04d}", rnd.choice(cuss)[0], rnd.choice(deps)[0], rnd.choice(persons)[0],
                        _dt(ANCHOR - timedelta(days=rnd.randint(0, 30))), 1))
        for _ in range(rnd.randint(1, 3)):
            m = rnd.choice(mats)
            so_det.append((i, m[0], rnd.randint(5, 200), round(rnd.uniform(10, 500), 2),
                           _dt(ANCHOR + timedelta(days=rnd.randint(1, 20)))))
    dl_main, dl_det = [], []
    for i in range(1, 9):
        so_idx = rnd.randint(1, 12)
        dl_main.append((f"U8DL{i:04d}", so_main[so_idx - 1][1], f"U8SO{so_idx:04d}",
                        _dt(ANCHOR - timedelta(days=rnd.randint(0, 10)))))
        for _ in range(rnd.randint(1, 2)):
            m = rnd.choice(mats)
            dl_det.append((i, m[0], rnd.randint(1, 100), round(rnd.uniform(10, 500), 2)))
    po_main, po_det = [], []
    for i in range(1, 11):
        po_main.append((f"U8PO{i:04d}", rnd.choice(vens)[0],
                        _dt(ANCHOR - timedelta(days=rnd.randint(0, 45))), 1))
        for _ in range(rnd.randint(1, 3)):
            m = rnd.choice(mats)
            po_det.append((i, m[0], rnd.randint(20, 500), round(rnd.uniform(5, 300), 2),
                           _dt(ANCHOR + timedelta(days=rnd.randint(3, 30)))))
    return {
        "Inventory": (["cInvCode", "cInvName", "cInvStd", "cInvCCode", "cComUnitCode", "iSafeNum", "dModifyDate"], mats),
        "Vendor": (["cVenCode", "cVenName", "cVenAbbName", "cVenPerson", "cVenPhone", "dModifyDate"], vens),
        "Customer": (["cCusCode", "cCusName", "cCusAbbName", "cCusPerson", "cCusPhone", "iCusCreLine", "dModifyDate"], cuss),
        "Warehouse": (["cWhCode", "cWhName", "cWhAddress", "dModifyDate"],
                      [(w, n, a, _dt(ANCHOR - timedelta(days=60))) for w, n, a in whs]),
        "Department": (["cDepCode", "cDepName", "dModifyDate"],
                       [(c, n, _dt(ANCHOR - timedelta(days=60))) for c, n in deps]),
        "Person": (["cPersonCode", "cPersonName", "cDepCode", "cPersonPhone", "dModifyDate"],
                   [(*p, _dt(ANCHOR - timedelta(days=60))) for p in persons]),
        "ComputationUnit": (["cComunitCode", "cComunitName", "dModifyDate"],
                            [(c, n, _dt(ANCHOR - timedelta(days=60))) for c, n in units]),
        "CurrentStock": (["cWhCode", "cInvCode", "iQuantity"], stock),
        "SO_SOMain": (["cSOCode", "cCusCode", "cDepCode", "cPersonCode", "dDate", "cState"], so_main),
        "SO_SODetails": (["ID", "cInvCode", "iQuantity", "iTaxUnitPrice", "dPreDate"], so_det),
        "DispatchList": (["cDLCode", "cCusCode", "cSOCode", "dDate"], dl_main),
        "DispatchLists": (["DLID", "cInvCode", "iQuantity", "iTaxUnitPrice"], dl_det),
        "PO_Pomain": (["cPOID", "cVenCode", "dPODate", "cState"], po_main),
        "PO_Podetails": (["POID", "cInvCode", "iQuantity", "iUnitPrice", "dArriveDate"], po_det),
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"仿真 U8：目标 {SRC_MSSQL_HOST or '127.0.0.1'}:{SRC_MSSQL_PORT} / {DB}")
    c = _connect("master")
    cur = c.cursor()
    cur.execute(f"IF DB_ID('{DB}') IS NULL CREATE DATABASE [{DB}]")
    c.close()

    c = _connect(DB)
    cur = c.cursor()
    data = _gen_rows()
    for name, ddl in TABLES_DDL.items():
        cur.execute(f"IF OBJECT_ID('{name}','U') IS NOT NULL DROP TABLE [{name}]")
        cur.execute(ddl)
        cols, rows = data[name]
        if rows:
            ph = ", ".join(["%s"] * len(cols))
            collist = ", ".join(f"[{x}]" for x in cols)
            cur.executemany(f"INSERT INTO [{name}] ({collist}) VALUES ({ph})", rows)
        print(f"  {name:16} {len(rows):4} 行")
    c.close()
    print(f"=== 仿真 U8 就绪：{DB} 共 {len(TABLES_DDL)} 表 ===")


if __name__ == "__main__":
    main()
