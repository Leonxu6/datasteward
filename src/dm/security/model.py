"""权限模型（对标 Palantir 两层安全）。

两层合取（AND），任何访问必须**同时**通过：
1. **强制层（Mandatory / Markings）**——否决式、集中管理、Owner 也绕不过；all-or-nothing 合取：
   资源上所有 Marking 用户都得有，缺一个连"存在"都看不到（discovery restriction）。
2. **自主层（Discretionary / Roles）**——只增不减；角色授予对某类操作的可见/可执行。

粒度：对象策略=行级、属性策略=列级、两者叠加=单元格级。写回权限**独立于读权限**。
见 docs/design/05-权限与Markings.md。

本模块只放**注册表与数据模型**；判定引擎见 policy.py。内置的角色/打标为示例，
真实部署从配置/DB 加载即可。
"""
from dataclasses import dataclass, field

# ---- Markings（强制层，all-or-nothing 合取）----
MARKINGS = {
    "PII": "个人隐私（联系人/电话等）",
    "FIN": "财务敏感（价格/信用额度等）",
    "U8": "用友 U8 源数据（客户 ERP 溯源标——沿血缘传播到全部下游）",
}

# ---- 角色（自主层）----
ROLES = ["采购", "仓管", "生产", "管理层", "管理员"]

# 角色 → 其成员天然具备的 Markings 资格（≈ 用户被授予的 marking）
# 设计：采购看价格(FIN)不看隐私(PII)；仓管/生产只看业务量，无敏感；管理层/管理员全看。
# U8 标全角色授予：目的是"数据来源可溯 + 审计里可见命中"，而非拦人——
# 若锁死，U8 标会沿血缘把整个 DW 层（DWD/DWS/ADS）对仓管/生产屏蔽。
ROLE_MARKINGS = {
    "管理员": {"PII", "FIN", "U8"},
    "管理层": {"PII", "FIN", "U8"},
    "采购": {"FIN", "U8"},
    "仓管": {"U8"},
    "生产": {"U8"},
}

# ---- 列级打标（属性安全策略 → 列级）：(表, 列) -> [markings] ----
COLUMN_MARKINGS = {
    ("employee", "phone"): ["PII"],
    ("supplier", "contact"): ["PII"],
    ("supplier", "phone"): ["PII"],
    ("customer", "contact"): ["PII"],
    ("customer", "phone"): ["PII"],
    ("customer", "credit_limit"): ["FIN"],
    ("purchase_order", "unit_price"): ["FIN"],
    ("sales_order", "unit_price"): ["FIN"],
}

# ---- 表级（对象级）打标：table -> [markings]（默认空；也会叠加"沿血缘传播"的有效 Markings）----
TABLE_MARKINGS: dict = {}

# ---- PBAC（purpose-based）：某些 Marking 的访问需正当"目的"。marking -> 允许的目的集合 ----
# 即使角色具备该 Marking，若本次访问目的不在允许集合内，其对该 Marking 的资格在本次访问中失效
# （对标 Palantir "授权给目的、不多不少、须记 rationale、可审计为何获权"）。
PURPOSE_REQUIRED = {
    "FIN": {"授信审核", "财务对账", "风控", "审批"},
    # PII 未列 → 不施加目的限制（仅受角色 Marking 约束）
}

# ---- 行级对象安全策略（Palantir object policy = 行级）：table -> 规则 ----
# 规则含义：指定角色只能看到该表中 column == 用户属性(attr) 的行；其它角色不受此行策略限制。
# 与列级属性策略叠加即"单元格级"。
ROW_POLICIES = {
    "inventory": {"role": "仓管", "column": "warehouse_id", "attr": "warehouse_id"},
}

# ---- 写回 Action 的执行权限（独立于读）：action -> {roles, markings} ----
ACTION_PERMISSIONS = {
    "adjust_safety_stock": {"roles": {"采购", "管理层", "管理员"}, "markings": set()},
    "create_purchase_requisition": {"roles": {"采购", "管理层", "管理员"}, "markings": set()},
    "create_delivery": {"roles": {"仓管", "管理层", "管理员"}, "markings": set()},
}


@dataclass
class User:
    """访问主体：角色 + 目的（PBAC）+ 属性（行级策略用）。Marking 资格由角色推导。"""
    name: str
    role: str = "仓管"
    purpose: str = ""          # PBAC：本次访问目的（记入审计的 why）
    attrs: dict = field(default_factory=dict)   # 行级属性，如 {"warehouse_id": "W02"}

    @property
    def markings(self) -> set:
        return set(ROLE_MARKINGS.get(self.role, set()))


def column_markings(table: str, column: str) -> list:
    return COLUMN_MARKINGS.get((table, column), [])


def table_markings(table: str) -> list:
    return TABLE_MARKINGS.get(table, [])
