"""单一 schema 定义：驱动 建表 / 造数 / MCP introspection / eval 标准答案。

19 类基础数据，来自《MES与ERP(用友U8)交互流程及接口确认列表(确认版)》。
每张表给"代表性字段 + 真实外键关系"。字段为本 PoC 的合成设计，**非 U8 真实 DDL**；
拿到真实 DDL 后逐表补字段即可，表已在此。

数据结构：
  TABLES: 19 张业务表，每张 = {name, cn, desc, pk, columns:[(列名, SQL类型, 中文名)], fks:[(列, 引用表)]}
  META_TABLES: 3 张留痕/评测表（审计、任务链、eval），由 connector/agent/eval 写入
"""

TABLES = [
    {
        "name": "company_org", "cn": "公司组织信息", "desc": "公司/分支机构组织信息（可层级）",
        "pk": "org_id",
        "columns": [
            ("org_id", "VARCHAR", "组织编码"),
            ("name", "VARCHAR", "组织名称"),
            ("parent_id", "VARCHAR", "上级组织"),
            ("org_type", "VARCHAR", "组织类型"),
        ],
        "fks": [("parent_id", "company_org")],
    },
    {
        "name": "department", "cn": "部门", "desc": "部门信息，挂在组织下",
        "pk": "dept_id",
        "columns": [
            ("dept_id", "VARCHAR", "部门编码"),
            ("name", "VARCHAR", "部门名称"),
            ("org_id", "VARCHAR", "所属组织"),
            ("parent_id", "VARCHAR", "上级部门"),
            ("manager", "VARCHAR", "负责人"),
        ],
        "fks": [("org_id", "company_org"), ("parent_id", "department")],
    },
    {
        "name": "employee", "cn": "职员信息", "desc": "员工花名册",
        "pk": "emp_id",
        "columns": [
            ("emp_id", "VARCHAR", "工号"),
            ("name", "VARCHAR", "姓名"),
            ("dept_id", "VARCHAR", "所属部门"),
            ("position", "VARCHAR", "岗位"),
            ("phone", "VARCHAR", "电话"),
            ("status", "VARCHAR", "在职状态"),
        ],
        "fks": [("dept_id", "department")],
    },
    {
        "name": "unit", "cn": "单位", "desc": "计量单位",
        "pk": "unit_id",
        "columns": [
            ("unit_id", "VARCHAR", "单位编码"),
            ("name", "VARCHAR", "单位名称"),
            ("symbol", "VARCHAR", "符号"),
        ],
        "fks": [],
    },
    {
        "name": "material_category", "cn": "物料分类体系", "desc": "物料分类（可层级）",
        "pk": "category_id",
        "columns": [
            ("category_id", "VARCHAR", "分类编码"),
            ("name", "VARCHAR", "分类名称"),
            ("parent_id", "VARCHAR", "上级分类"),
        ],
        "fks": [("parent_id", "material_category")],
    },
    {
        "name": "material", "cn": "物料信息", "desc": "物料主数据：编码/名称/规格/分类/基本单位/安全库存",
        "pk": "material_id",
        "columns": [
            ("material_id", "VARCHAR", "物料编码"),
            ("name", "VARCHAR", "物料名称"),
            ("spec", "VARCHAR", "规格型号"),
            ("category_id", "VARCHAR", "物料分类"),
            ("base_unit_id", "VARCHAR", "基本单位"),
            ("material_type", "VARCHAR", "物料类型"),
            ("safety_stock", "INTEGER", "安全库存"),
        ],
        "fks": [("category_id", "material_category"), ("base_unit_id", "unit")],
    },
    {
        "name": "unit_conversion", "cn": "单位转换率", "desc": "多单位换算（物料级或通用）",
        "pk": "id",
        "columns": [
            ("id", "VARCHAR", "编码"),
            ("material_id", "VARCHAR", "物料"),
            ("from_unit_id", "VARCHAR", "源单位"),
            ("to_unit_id", "VARCHAR", "目标单位"),
            ("factor", "INTEGER", "换算率"),
        ],
        "fks": [("material_id", "material"), ("from_unit_id", "unit"), ("to_unit_id", "unit")],
    },
    {
        "name": "warehouse", "cn": "仓库", "desc": "仓库主数据",
        "pk": "warehouse_id",
        "columns": [
            ("warehouse_id", "VARCHAR", "仓库编码"),
            ("name", "VARCHAR", "仓库名称"),
            ("type", "VARCHAR", "仓库类型"),
        ],
        "fks": [],
    },
    {
        "name": "storage_location", "cn": "库位", "desc": "仓库下的库位",
        "pk": "location_id",
        "columns": [
            ("location_id", "VARCHAR", "库位编码"),
            ("warehouse_id", "VARCHAR", "所属仓库"),
            ("code", "VARCHAR", "库位代号"),
            ("name", "VARCHAR", "库位名称"),
        ],
        "fks": [("warehouse_id", "warehouse")],
    },
    {
        "name": "supplier", "cn": "供应商", "desc": "供应商主数据",
        "pk": "supplier_id",
        "columns": [
            ("supplier_id", "VARCHAR", "供应商编码"),
            ("name", "VARCHAR", "供应商名称"),
            ("contact", "VARCHAR", "联系人"),
            ("phone", "VARCHAR", "电话"),
            ("address", "VARCHAR", "地址"),
        ],
        "fks": [],
    },
    {
        "name": "customer", "cn": "客户", "desc": "客户主数据",
        "pk": "customer_id",
        "columns": [
            ("customer_id", "VARCHAR", "客户编码"),
            ("name", "VARCHAR", "客户名称"),
            ("contact", "VARCHAR", "联系人"),
            ("phone", "VARCHAR", "电话"),
            ("credit_limit", "INTEGER", "信用额度"),
        ],
        "fks": [],
    },
    {
        "name": "dictionary", "cn": "字典", "desc": "各种单据分类/枚举",
        "pk": "dict_id",
        "columns": [
            ("dict_id", "VARCHAR", "字典编码"),
            ("dict_type", "VARCHAR", "字典类型"),
            ("code", "VARCHAR", "代码"),
            ("value", "VARCHAR", "值"),
            ("description", "VARCHAR", "说明"),
        ],
        "fks": [],
    },
    {
        "name": "inventory", "cn": "即时库存信息", "desc": "即时库存：物料×仓库×库位 的当前数量",
        "pk": "id",
        "columns": [
            ("id", "VARCHAR", "记录编码"),
            ("material_id", "VARCHAR", "物料"),
            ("warehouse_id", "VARCHAR", "仓库"),
            ("location_id", "VARCHAR", "库位"),
            ("qty", "INTEGER", "数量"),
            ("batch_no", "VARCHAR", "批次号"),
            ("update_time", "TIMESTAMP", "更新时间"),
        ],
        "fks": [("material_id", "material"), ("warehouse_id", "warehouse"), ("location_id", "storage_location")],
    },
    {
        "name": "purchase_order", "cn": "采购单", "desc": "采购订单（行级：一行一物料）",
        "pk": "po_id+line_no",
        "columns": [
            ("po_id", "VARCHAR", "采购单号"),
            ("line_no", "INTEGER", "行号"),
            ("supplier_id", "VARCHAR", "供应商"),
            ("material_id", "VARCHAR", "物料"),
            ("qty", "INTEGER", "数量"),
            ("unit_price", "DOUBLE", "单价"),
            ("order_date", "DATE", "下单日期"),
            ("expected_date", "DATE", "预计到货"),
            ("status", "VARCHAR", "状态"),
        ],
        "fks": [("supplier_id", "supplier"), ("material_id", "material")],
    },
    {
        "name": "purchase_arrival", "cn": "采购到货单", "desc": "采购到货（关联采购单）",
        "pk": "arrival_id",
        "columns": [
            ("arrival_id", "VARCHAR", "到货单号"),
            ("po_id", "VARCHAR", "采购单号"),
            ("supplier_id", "VARCHAR", "供应商"),
            ("material_id", "VARCHAR", "物料"),
            ("arrived_qty", "INTEGER", "到货数量"),
            ("arrival_date", "DATE", "到货日期"),
            ("status", "VARCHAR", "状态"),
        ],
        "fks": [("po_id", "purchase_order"), ("supplier_id", "supplier"), ("material_id", "material")],
    },
    {
        "name": "sales_order", "cn": "销售订单", "desc": "销售订单（行级：一行一物料）",
        "pk": "so_id+line_no",
        "columns": [
            ("so_id", "VARCHAR", "销售单号"),
            ("line_no", "INTEGER", "行号"),
            ("customer_id", "VARCHAR", "客户"),
            ("material_id", "VARCHAR", "物料"),
            ("qty", "INTEGER", "数量"),
            ("unit_price", "DOUBLE", "单价"),
            ("order_date", "DATE", "下单日期"),
            ("delivery_date", "DATE", "要求交货"),
            ("status", "VARCHAR", "状态"),
        ],
        "fks": [("customer_id", "customer"), ("material_id", "material")],
    },
    {
        "name": "delivery_note", "cn": "发货单", "desc": "发货通知（关联销售订单）",
        "pk": "delivery_id",
        "columns": [
            ("delivery_id", "VARCHAR", "发货单号"),
            ("so_id", "VARCHAR", "销售单号"),
            ("customer_id", "VARCHAR", "客户"),
            ("material_id", "VARCHAR", "物料"),
            ("qty", "INTEGER", "发货数量"),
            ("delivery_date", "DATE", "发货日期"),
            ("status", "VARCHAR", "状态"),
        ],
        "fks": [("so_id", "sales_order"), ("customer_id", "customer"), ("material_id", "material")],
    },
    {
        "name": "production_order", "cn": "生产订单", "desc": "生产工单（一单一成品）",
        "pk": "mo_id",
        "columns": [
            ("mo_id", "VARCHAR", "生产单号"),
            ("material_id", "VARCHAR", "成品物料"),
            ("planned_qty", "INTEGER", "计划数量"),
            ("completed_qty", "INTEGER", "已完工数量"),
            ("start_date", "DATE", "开工日期"),
            ("due_date", "DATE", "交期"),
            ("status", "VARCHAR", "状态"),
        ],
        "fks": [("material_id", "material")],
    },
    {
        "name": "production_material_req", "cn": "生产订单用料分析表", "desc": "生产工单子件清单（BOM 展开用料）",
        "pk": "id",
        "columns": [
            ("id", "VARCHAR", "编码"),
            ("mo_id", "VARCHAR", "生产单号"),
            ("material_id", "VARCHAR", "子件物料"),
            ("required_qty", "INTEGER", "应领数量"),
            ("issued_qty", "INTEGER", "已领数量"),
        ],
        "fks": [("mo_id", "production_order"), ("material_id", "material")],
    },
]

META_TABLES = [
    {
        "name": "audit_log", "cn": "审计日志", "desc": "MCP 连接器每次工具调用留痕",
        "pk": "audit_id",
        "columns": [
            ("audit_id", "VARCHAR", "审计编码"),
            ("ts", "TIMESTAMP", "时间"),
            ("session_id", "VARCHAR", "会话"),
            ("channel", "VARCHAR", "通道"),
            ("user", "VARCHAR", "用户"),
            ("tool_name", "VARCHAR", "工具"),
            ("tool_args", "VARCHAR", "参数"),
            ("sql", "VARCHAR", "执行SQL"),
            ("tables_touched", "VARCHAR", "命中表"),
            ("row_count", "INTEGER", "返回行数"),
            ("duration_ms", "INTEGER", "耗时ms"),
            ("ok", "BOOLEAN", "成功"),
            ("error", "VARCHAR", "错误"),
        ],
        "fks": [],
    },
    {
        "name": "agent_session", "cn": "智能体任务链", "desc": "智能体每一步决策留痕",
        "pk": "rowid",
        "columns": [
            ("session_id", "VARCHAR", "会话"),
            ("ts", "TIMESTAMP", "时间"),
            ("channel", "VARCHAR", "通道"),
            ("question", "VARCHAR", "问题"),
            ("step_no", "INTEGER", "步序"),
            ("step_type", "VARCHAR", "步骤类型"),
            ("content", "VARCHAR", "内容"),
            ("final_answer", "VARCHAR", "最终答案"),
        ],
        "fks": [],
    },
    {
        "name": "eval_run", "cn": "评测结果", "desc": "eval 跑批逐条结果",
        "pk": "rowid",
        "columns": [
            ("run_id", "VARCHAR", "跑批编码"),
            ("case_id", "VARCHAR", "用例"),
            ("category", "VARCHAR", "类别"),
            ("question", "VARCHAR", "问题"),
            ("expected", "VARCHAR", "期望"),
            ("got", "VARCHAR", "实际"),
            ("grader", "VARCHAR", "判分方式"),
            ("passed", "BOOLEAN", "通过"),
            ("session_id", "VARCHAR", "会话"),
            ("ts", "TIMESTAMP", "时间"),
        ],
        "fks": [],
    },
]

ALL_TABLES = TABLES + META_TABLES


def table_by_name(name):
    for t in ALL_TABLES:
        if t["name"] == name:
            return t
    return None


def business_table_names():
    return [t["name"] for t in TABLES]
