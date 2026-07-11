"""按 schema 生成内部一致的合成数据（PoC 用；将来可替换为真实 U8/API 源适配器）。

固定随机种子 → 可复现，便于 eval 用 SQL 算标准答案做自动比对。
内部一致性保证：
  - 每个物料都有 1~3 条即时库存（库存类问题必有解）
  - 单据行引用的物料/供应商/客户均真实存在
"""
import random
from datetime import date, datetime, timedelta

from faker import Faker

SEED = 42
TODAY = date(2026, 6, 25)  # 固定日期保证复现性：eval 的 SQL 标准答案依赖此值，请勿改为 date.today()


def _date(rng, lo, hi):
    return TODAY + timedelta(days=rng.randint(lo, hi))


def _dt(rng):
    return datetime(2026, 6, 25, 8, 0, 0) - timedelta(days=rng.randint(0, 30), hours=rng.randint(0, 23))


def build_all():
    rng = random.Random(SEED)
    Faker.seed(SEED)
    fake = Faker("zh_CN")
    data = {}

    # 公司组织信息（虚构示例企业，与任何真实公司无关）
    orgs = ["云帆智能装备有限公司", "云帆华东制造中心", "云帆研发中心"]
    org_ids = [f"ORG{i:02d}" for i in range(1, len(orgs) + 1)]
    data["company_org"] = [
        {"org_id": oid, "name": nm, "parent_id": (None if i == 0 else org_ids[0]),
         "org_type": ("集团" if i == 0 else "分支机构")}
        for i, (oid, nm) in enumerate(zip(org_ids, orgs))
    ]

    # 部门
    depts = ["生产部", "仓储部", "采购部", "销售部", "品质部", "研发部", "财务部", "人事部"]
    dept_ids = [f"D{i:03d}" for i in range(1, len(depts) + 1)]
    data["department"] = [
        {"dept_id": did, "name": nm, "org_id": org_ids[0], "parent_id": None, "manager": fake.name()}
        for did, nm in zip(dept_ids, depts)
    ]

    # 职员信息
    data["employee"] = [
        {"emp_id": f"E{i:04d}", "name": fake.name(), "dept_id": rng.choice(dept_ids),
         "position": rng.choice(["主管", "专员", "经理", "操作工", "工程师"]),
         "phone": fake.phone_number(),
         "status": rng.choices(["在职", "离职"], weights=[9, 1])[0]}
        for i in range(1, 31)
    ]

    # 单位
    units = [("U01", "个", "PCS"), ("U02", "千克", "KG"), ("U03", "米", "M"),
             ("U04", "台", "SET"), ("U05", "箱", "CTN"), ("U06", "升", "L")]
    unit_ids = [u[0] for u in units]
    data["unit"] = [{"unit_id": u[0], "name": u[1], "symbol": u[2]} for u in units]

    # 物料分类体系
    cats = [("C01", "原材料", None), ("C02", "金属材料", "C01"), ("C03", "电子元件", "C01"),
            ("C04", "标准件", "C01"), ("C05", "半成品", None), ("C06", "成品", None),
            ("C07", "包装材料", None), ("C08", "辅料", None)]
    cat_ids = [c[0] for c in cats]
    data["material_category"] = [{"category_id": c[0], "name": c[1], "parent_id": c[2]} for c in cats]

    # 物料信息
    n_mat = 50
    mat_ids = [f"M{i:04d}" for i in range(1, n_mat + 1)]
    adj = ["精密", "标准", "通用", "重型", "轻型", "高强"]
    noun = ["轴承", "电机", "齿轮", "支架", "控制器", "螺栓", "外壳", "线缆", "传感器", "面板", "联轴器", "阀体"]
    materials = []
    for i, mid in enumerate(mat_ids, 1):
        materials.append({
            "material_id": mid,
            "name": f"{rng.choice(adj)}{rng.choice(noun)}{i:03d}",
            "spec": f"{rng.choice(['A', 'B', 'C'])}-{rng.randint(10, 999)}",
            "category_id": rng.choice(cat_ids),
            "base_unit_id": rng.choice(unit_ids),
            "material_type": rng.choice(["原材料", "半成品", "成品"]),
            "safety_stock": rng.choice([0, 10, 20, 50, 100]),
        })
    data["material"] = materials

    # 单位转换率
    uc = []
    for i in range(1, 11):
        a, b = rng.sample(unit_ids, 2)
        uc.append({"id": f"UC{i:03d}", "material_id": rng.choice(mat_ids),
                   "from_unit_id": a, "to_unit_id": b, "factor": rng.choice([10, 12, 24, 100, 1000])})
    data["unit_conversion"] = uc

    # 仓库
    whs = [("W01", "原材料仓", "原料"), ("W02", "半成品仓", "半成品"),
           ("W03", "成品仓", "成品"), ("W04", "委外仓", "委外")]
    wh_ids = [w[0] for w in whs]
    data["warehouse"] = [{"warehouse_id": w[0], "name": w[1], "type": w[2]} for w in whs]

    # 库位
    loc_rows = []
    locs_by_wh = {}
    k = 1
    for w in wh_ids:
        for j in range(1, 4):
            lid = f"L{k:03d}"
            k += 1
            loc_rows.append({"location_id": lid, "warehouse_id": w, "code": f"{w}-{j:02d}", "name": f"{w}区{j}号位"})
            locs_by_wh.setdefault(w, []).append(lid)
    data["storage_location"] = loc_rows

    # 供应商
    sup_ids = [f"S{i:03d}" for i in range(1, 16)]
    data["supplier"] = [{"supplier_id": s, "name": fake.company(), "contact": fake.name(),
                         "phone": fake.phone_number(), "address": fake.city()} for s in sup_ids]

    # 客户
    cus_ids = [f"K{i:03d}" for i in range(1, 16)]
    data["customer"] = [{"customer_id": c, "name": fake.company(), "contact": fake.name(),
                         "phone": fake.phone_number(), "credit_limit": rng.choice([0, 100000, 500000, 1000000])}
                        for c in cus_ids]

    # 字典
    dtypes = {"采购订单状态": ["未完成", "已完成", "已取消"], "销售订单状态": ["未完成", "已完成", "已取消"],
              "出库类别": ["生产领料", "销售出库", "其他出库"], "入库类别": ["采购入库", "产成品入库", "其他入库"],
              "物料类型": ["原材料", "半成品", "成品"]}
    drows = []
    di = 1
    for dt, vals in dtypes.items():
        for ci, v in enumerate(vals, 1):
            drows.append({"dict_id": f"DCT{di:03d}", "dict_type": dt, "code": f"{ci:02d}",
                          "value": v, "description": f"{dt}-{v}"})
            di += 1
    data["dictionary"] = drows

    # 即时库存信息（每个物料 1~3 行，保证每个物料都有库存）
    inv = []
    ii = 1
    for mid in mat_ids:
        for _ in range(rng.randint(1, 3)):
            w = rng.choice(wh_ids)
            lid = rng.choice(locs_by_wh[w])
            inv.append({"id": f"INV{ii:05d}", "material_id": mid, "warehouse_id": w, "location_id": lid,
                        "qty": rng.randint(0, 500), "batch_no": f"B{rng.randint(2025, 2026)}{rng.randint(1000, 9999)}",
                        "update_time": _dt(rng)})
            ii += 1
    data["inventory"] = inv

    # 采购单（按单多行）
    po_ids = [f"PO{i:04d}" for i in range(1, 31)]
    po = []
    for pid in po_ids:
        sup = rng.choice(sup_ids)
        od = _date(rng, -120, 0)
        st = rng.choices(["未完成", "已完成", "已取消"], weights=[5, 4, 1])[0]
        for ln in range(1, rng.randint(1, 4) + 1):
            po.append({"po_id": pid, "line_no": ln, "supplier_id": sup, "material_id": rng.choice(mat_ids),
                       "qty": rng.randint(10, 1000), "unit_price": round(rng.uniform(1, 500), 2),
                       "order_date": od, "expected_date": od + timedelta(days=rng.randint(7, 30)), "status": st})
    data["purchase_order"] = po

    # 采购到货单
    # 时间一致性：rng 调用的顺序/参数与旧版逐一对齐（先量后日期再状态），保证随机流不漂移
    # ——稳定测试 ID（M0001/SO0001/S001）与 eval 真值依赖同一随机流。未来日期仅事后矫正状态。
    pa = []
    for i in range(1, 26):
        pid = rng.choice(po_ids)
        line = rng.choice([r for r in po if r["po_id"] == pid])
        arrived_qty = rng.randint(5, max(5, line["qty"]))
        a_date = line["order_date"] + timedelta(days=rng.randint(5, 25))
        st = rng.choice(["待检", "合格", "入库"])
        if a_date > TODAY:
            st = "待检"  # 未来的到货（在途预告）不可能已质检/入库
        pa.append({"arrival_id": f"PA{i:04d}", "po_id": pid, "supplier_id": line["supplier_id"],
                   "material_id": line["material_id"], "arrived_qty": arrived_qty,
                   "arrival_date": a_date, "status": st})
    data["purchase_arrival"] = pa

    # 销售订单（按单多行）
    so_ids = [f"SO{i:04d}" for i in range(1, 31)]
    so = []
    for sid in so_ids:
        cus = rng.choice(cus_ids)
        od = _date(rng, -90, 0)
        st = rng.choices(["未完成", "已完成", "已取消"], weights=[6, 3, 1])[0]
        for ln in range(1, rng.randint(1, 4) + 1):
            so.append({"so_id": sid, "line_no": ln, "customer_id": cus, "material_id": rng.choice(mat_ids),
                       "qty": rng.randint(1, 300), "unit_price": round(rng.uniform(10, 2000), 2),
                       "order_date": od, "delivery_date": od + timedelta(days=rng.randint(7, 45)), "status": st})
    data["sales_order"] = so

    # 发货单（rng 顺序对齐旧版，同上）
    dn = []
    for i in range(1, 26):
        sid = rng.choice(so_ids)
        line = rng.choice([r for r in so if r["so_id"] == sid])
        qty = rng.randint(1, max(1, line["qty"]))
        d_date = line["order_date"] + timedelta(days=rng.randint(5, 40))
        st = rng.choice(["待发", "已发货", "已签收"])
        if d_date > TODAY:
            st = "待发"  # 发货日期还没到，不可能已发货/已签收（曾致"明天的发货已签收"怪答案）
        dn.append({"delivery_id": f"DN{i:04d}", "so_id": sid, "customer_id": line["customer_id"],
                   "material_id": line["material_id"], "qty": qty,
                   "delivery_date": d_date, "status": st})
    data["delivery_note"] = dn

    # 生产订单
    mo_ids = [f"MO{i:04d}" for i in range(1, 21)]
    finished = [m["material_id"] for m in materials if m["material_type"] in ("半成品", "成品")] or mat_ids
    mo = []
    for mid in mo_ids:
        sd = _date(rng, -60, 10)
        planned = rng.randint(10, 200)
        comp = rng.randint(0, planned)
        mo.append({"mo_id": mid, "material_id": rng.choice(finished), "planned_qty": planned, "completed_qty": comp,
                   "start_date": sd, "due_date": sd + timedelta(days=rng.randint(5, 30)),
                   "status": rng.choice(["计划", "生产中", "已完工"])})
    data["production_order"] = mo

    # 生产订单用料分析表（子件清单）
    raws = [m["material_id"] for m in materials if m["material_type"] == "原材料"] or mat_ids
    pmr = []
    pi = 1
    for m in mo:
        for _ in range(rng.randint(2, 5)):
            req = rng.randint(1, 50)
            pmr.append({"id": f"PMR{pi:05d}", "mo_id": m["mo_id"], "material_id": rng.choice(raws),
                        "required_qty": req, "issued_qty": rng.randint(0, req)})
            pi += 1
    data["production_material_req"] = pmr

    return data


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    d = build_all()
    for k, v in d.items():
        print(f"{k}: {len(v)} 行")
