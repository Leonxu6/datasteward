"""合成"与数仓实体挂钩"的非结构化文档（S2）。

文档引用真实存在的物料/供应商/订单/到货 ID（与 StarRocks/Postgres 同一批 build_all 实体），
覆盖五类：采购框架合同 / 作业指导书SOP / 进货检验质检报告 / 设备维护手册 / 物料技术规格书。
其中刻意嵌入**可核对的确定性事实**（违约金比例、公差、保养周期、不良率、保质期…），
供 RAG eval 断言"智能体是否检索到正确文档并据此作答"。文档还引用了 ERP 里没有的关系
（如设备 CNC-08 ↔ 物料 M0001），为 S3 知识图谱的"文档抽取新关系"埋下接缝。

落地：写 .md 文件到 DM_DATA_DIR/docs/ + 注册到 Postgres `document` 表（含 content-hash）。
用法（一般由 dm-docs 调用）：python -m dm.docs.generate_docs
"""
import hashlib
import sys

from dm.config import DATA_DIR
from dm.docs.store import connect, init_schema
from dm.warehouse.generate import build_all

DOCS_DIR = DATA_DIR / "rag_docs"  # 合成文档落数据目录（非仓库 docs/，避免污染真实文档），可由 dm-docs 重生成


def build_documents():
    """返回 [{doc_id, doc_type, title, entities:[...], body}]，确定性、引用真实实体。"""
    data = build_all()
    mat = {m["material_id"]: m for m in data["material"]}
    sup = {s["supplier_id"]: s for s in data["supplier"]}

    def mname(mid):
        return mat.get(mid, {}).get("name", mid)

    def sname(sid):
        return sup.get(sid, {}).get("name", sid)

    docs = []

    # ---------- 采购框架合同（含违约金 / 账期 / 质保等确定性条款） ----------
    docs.append({
        "doc_id": "DOC0001", "doc_type": "contract",
        "title": f"供应商 {sname('S001')}（S001）年度采购框架合同",
        "entities": ["S001", "M0003", "M0007"],
        "body": (
            f"# 年度采购框架合同（编号 HT-2026-001）\n"
            f"关联实体：供应商 S001（{sname('S001')}）；物料 M0003（{mname('M0003')}）、M0007（{mname('M0007')}）\n\n"
            "## 一、合作范围\n"
            f"甲方云帆智能装备有限公司向乙方 {sname('S001')} 采购物料 M0003、M0007 及其同类金属件，"
            "本合同为年度框架协议，具体数量与交期以逐次下达的采购订单为准。\n\n"
            "## 二、价格与账期\n"
            "含税单价自合同生效之日起锁定 6 个月；结算账期为月结 60 天，乙方按月开具增值税专用发票。\n\n"
            "## 三、交货与逾期违约\n"
            "乙方应按采购订单约定的预计到货日交货。若逾期交货，每延迟一日按未交付部分金额的 0.5% 向甲方支付违约金，"
            "违约金累计封顶为该批次合同金额的 5%；逾期超过 15 日，甲方有权解除对应订单并另行采购，差价由乙方承担。\n\n"
            "## 四、质量与质保\n"
            "到货执行进货检验，验收标准依据 GB/T 2828.1 一般检验水平 II、AQL 1.0；质保期为验收合格之日起 12 个月，"
            "质保期内非人为损坏由乙方免费更换。\n"
        ),
    })
    docs.append({
        "doc_id": "DOC0002", "doc_type": "contract",
        "title": f"供应商 {sname('S005')}（S005）采购框架合同",
        "entities": ["S005", "M0012"],
        "body": (
            f"# 采购框架合同（编号 HT-2026-005）\n"
            f"关联实体：供应商 S005（{sname('S005')}）；物料 M0012（{mname('M0012')}）\n\n"
            "## 价格与账期\n"
            f"乙方 {sname('S005')} 供应物料 M0012，结算账期月结 30 天，最小起订量（MOQ）为 200 件。\n\n"
            "## 逾期违约\n"
            "逾期交货每延迟一日按未交付金额的 0.3% 计违约金，累计封顶 8%。\n\n"
            "## 质保\n"
            "质保期 6 个月，验收标准 AQL 1.5。\n"
        ),
    })
    docs.append({
        "doc_id": "DOC0003", "doc_type": "contract",
        "title": f"供应商 {sname('S009')}（S009）采购框架合同",
        "entities": ["S009", "M0020", "M0021"],
        "body": (
            f"# 采购框架合同（编号 HT-2026-009）\n"
            f"关联实体：供应商 S009（{sname('S009')}）；物料 M0020、M0021\n\n"
            f"乙方 {sname('S009')} 供应电子元件类物料 M0020、M0021。含税单价锁定 6 个月，账期月结 45 天。"
            "逾期违约金每日 0.4%、封顶 6%。要求提供 RoHS 合规证明与每批次 COC 质量证明书。\n"
        ),
    })

    # ---------- 作业指导书 SOP（含工序 / 公差 / 设备等确定性参数） ----------
    docs.append({
        "doc_id": "DOC0004", "doc_type": "sop",
        "title": f"物料 M0001（{mname('M0001')}）精加工作业指导书",
        "entities": ["M0001", "CNC-08"],
        "body": (
            f"# 作业指导书 WI-M0001（{mname('M0001')} 精加工）\n"
            f"关联实体：物料 M0001（{mname('M0001')}）；关键设备 CNC-08 加工中心\n\n"
            "## 一、工序流程\n"
            "下料 → 粗加工 → 精加工 → 去毛刺 → 质检 → 入库。\n\n"
            "## 二、关键工艺参数\n"
            "精加工工序的尺寸公差要求为 ±0.02mm，表面粗糙度不低于 Ra1.6；精加工在 CNC-08 加工中心上完成，"
            "主轴转速 8000 rpm、进给速度 1200 mm/min。\n\n"
            "## 三、质量控制\n"
            "执行首件检验（首检）合格后方可批量加工，过程中每 2 小时巡检一次，关键尺寸 100% 自检。"
            "不合格品隔离并挂红牌，记录于质检台账。\n"
        ),
    })
    docs.append({
        "doc_id": "DOC0005", "doc_type": "sop",
        "title": f"物料 M0002（{mname('M0002')}）装配作业指导书",
        "entities": ["M0002", "ASSY-02"],
        "body": (
            f"# 作业指导书 WI-M0002（{mname('M0002')} 装配）\n"
            f"关联实体：物料 M0002（{mname('M0002')}）；设备 ASSY-02 装配线\n\n"
            "装配在 ASSY-02 装配线完成。紧固螺栓拧紧扭矩为 8.5 N·m，须使用带扭矩反馈的电动扭矩枪并每周校准。"
            "全线设 3 处防错（Poka-Yoke）检测点，漏装自动报警停线。\n"
        ),
    })

    # ---------- 进货 / 出货检验报告（含抽样 / 不良率 / 结论） ----------
    docs.append({
        "doc_id": "DOC0006", "doc_type": "quality",
        "title": "采购到货 PA0001 进货检验报告",
        "entities": ["PA0001", "S001", "M0003"],
        "body": (
            "# 进货检验报告 IQC-PA0001\n"
            f"关联实体：到货单 PA0001；供应商 S001（{sname('S001')}）；物料 M0003（{mname('M0003')}）\n\n"
            "依据 GB/T 2828.1 一般检验水平 II 抽样，抽样数 32 件。检出不良 2 件，不良率 6.25%，"
            "主要缺陷为尺寸超差（外径偏大 0.05mm）。经评审，缺陷不影响装配功能，结论为：让步接收（特采），"
            "并要求供应商提交 8D 改善报告。\n"
        ),
    })
    docs.append({
        "doc_id": "DOC0007", "doc_type": "quality",
        "title": "采购到货 PA0002 进货检验报告",
        "entities": ["PA0002", "M0007"],
        "body": (
            "# 进货检验报告 IQC-PA0002\n"
            "关联实体：到货单 PA0002；物料 M0007\n\n"
            "抽样数 50 件，检出不良 0 件，不良率 0%，外观、尺寸、硬度全部合格。结论：合格，正常入库。\n"
        ),
    })
    docs.append({
        "doc_id": "DOC0008", "doc_type": "quality",
        "title": "生产订单 MO0001 成品出货检验报告",
        "entities": ["MO0001", "M0001"],
        "body": (
            "# 出货检验报告 OQC-MO0001\n"
            "关联实体：生产订单 MO0001；成品物料 M0001\n\n"
            "对 MO0001 完工成品执行出货检验，关键尺寸全检、外观抽检 AQL 1.0。不良率 1.2%，"
            "返修后复检合格。结论：合格放行。\n"
        ),
    })

    # ---------- 设备维护手册（含保养周期 / 易损件 / 报警码） ----------
    docs.append({
        "doc_id": "DOC0009", "doc_type": "manual",
        "title": "CNC-08 加工中心维护保养手册",
        "entities": ["CNC-08", "M0001"],
        "body": (
            "# CNC-08 加工中心 维护保养手册\n"
            "关联实体：设备 CNC-08；服务物料 M0001 精加工工序\n\n"
            "## 保养周期\n"
            "每运行 500 小时更换一次主轴润滑油；每运行 2000 小时更换导轨滑块并检查丝杠间隙；每日班后清理铁屑与冷却液过滤网。\n\n"
            "## 常见报警\n"
            "报警代码 ALM-21 表示主轴过热，应停机检查冷却系统与主轴润滑油位；ALM-33 表示气压不足。\n"
        ),
    })
    docs.append({
        "doc_id": "DOC0010", "doc_type": "manual",
        "title": "ASSY-02 装配线维护手册",
        "entities": ["ASSY-02", "M0002"],
        "body": (
            "# ASSY-02 装配线 维护手册\n"
            "关联实体：设备 ASSY-02；服务物料 M0002 装配\n\n"
            "电动扭矩枪每周校准一次；气动接头为易损件，每 6 个月更换；每日点检急停与光栅保护。\n"
        ),
    })

    # ---------- 物料技术规格书（含材质 / 存储 / 保质期） ----------
    docs.append({
        "doc_id": "DOC0011", "doc_type": "spec",
        "title": f"物料 M0046（{mname('M0046')}）技术规格书",
        "entities": ["M0046"],
        "body": (
            f"# 技术规格书 SPEC-M0046（{mname('M0046')}）\n"
            "关联实体：物料 M0046\n\n"
            "材质为不锈钢 304；存储条件为干燥、避光，环境温度不超过 30℃，相对湿度 ≤60%；"
            "保质期 24 个月；出厂采用防潮膜真空包装，开封后须 7 日内使用。\n"
        ),
    })
    docs.append({
        "doc_id": "DOC0012", "doc_type": "spec",
        "title": f"物料 M0050（{mname('M0050')}）技术规格书",
        "entities": ["M0050"],
        "body": (
            f"# 技术规格书 SPEC-M0050（{mname('M0050')}）\n"
            "关联实体：物料 M0050\n\n"
            "材质为铝合金 6061-T6；表面阳极氧化处理，硬度 HB95；存储于常温干燥库房，避免与酸碱接触。\n"
        ),
    })

    # ---------- 仓储 SOP（与库房实体挂钩） ----------
    docs.append({
        "doc_id": "DOC0013", "doc_type": "sop",
        "title": "半成品仓 W02 库房管理 SOP",
        "entities": ["W02"],
        "body": (
            "# 库房管理作业规范 WI-W02（半成品仓）\n"
            "关联实体：仓库 W02（半成品仓）\n\n"
            "半成品仓 W02 执行先进先出（FIFO）发料原则；每日记录温湿度，温度宜 10~30℃；"
            "货架最大堆码层数为 5 层，超高须上架；批次混放需物理隔离并悬挂标识。\n"
        ),
    })

    # ---------- 补充合同 / 质检（增加检索区分度，非 eval 锚点） ----------
    for sid, mids, fee, cap, term in [
        ("S003", ["M0015"], "0.2%", "5%", "30 天"),
        ("S007", ["M0030", "M0031"], "0.5%", "10%", "60 天"),
        ("S012", ["M0040"], "0.3%", "5%", "45 天"),
    ]:
        n = sid[1:]
        docs.append({
            "doc_id": f"DOC01{n}", "doc_type": "contract",
            "title": f"供应商 {sname(sid)}（{sid}）采购框架合同",
            "entities": [sid] + mids,
            "body": (
                f"# 采购框架合同（编号 HT-2026-{n}）\n"
                f"关联实体：供应商 {sid}（{sname(sid)}）；物料 {'、'.join(mids)}\n\n"
                f"乙方 {sname(sid)} 供应物料 {'、'.join(mids)}。账期月结 {term}，逾期违约金每日 {fee}、累计封顶 {cap}。"
                "验收依据 GB/T 2828.1，AQL 1.0。\n"
            ),
        })

    return docs


def gen():
    """生成文档：写文件 + 注册到 document 表（content-hash），不做嵌入。返回文档列表。"""
    init_schema()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    docs = build_documents()
    c = connect()
    cur = c.cursor()
    for d in docs:
        body = d["body"]
        h = hashlib.sha256(body.encode("utf-8")).hexdigest()
        path = DOCS_DIR / f'{d["doc_id"]}_{d["doc_type"]}.md'
        path.write_text(body, encoding="utf-8")
        cur.execute(
            """INSERT INTO document(doc_id, doc_type, title, entities, source_path, content_hash)
               VALUES(%s,%s,%s,%s,%s,%s)
               ON CONFLICT(doc_id) DO UPDATE SET
                 doc_type=EXCLUDED.doc_type, title=EXCLUDED.title, entities=EXCLUDED.entities,
                 source_path=EXCLUDED.source_path, content_hash=EXCLUDED.content_hash""",
            (d["doc_id"], d["doc_type"], d["title"], ",".join(d["entities"]), str(path), h))
    c.close()
    return docs


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    docs = gen()
    print(f"=== 已合成并注册 {len(docs)} 篇文档到 document 表，文件落 {DOCS_DIR} ===")
    for d in docs:
        print(f'  {d["doc_id"]}  {d["doc_type"]:9} {d["title"]}  [{",".join(d["entities"])}]')


if __name__ == "__main__":
    main()
