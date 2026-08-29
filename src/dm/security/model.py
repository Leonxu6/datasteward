"""Permission model registries and lightweight access-subject types.

Policy evaluation lives in ``policy.py``. Helpers here deliberately return copies
of mutable registry values so a query path cannot accidentally rewrite global
security policy for later requests.
"""
from dataclasses import dataclass, field

MARKINGS = {
    "PII": "个人隐私（联系人/电话等）",
    "FIN": "财务敏感（价格/信用额度等）",
    "U8": "用友 U8 源数据（客户 ERP 溯源标——沿血缘传播到全部下游）",
}

ROLES = ["采购", "仓管", "生产", "管理层", "管理员"]

ROLE_MARKINGS = {
    "管理员": {"PII", "FIN", "U8"},
    "管理层": {"PII", "FIN", "U8"},
    "采购": {"FIN", "U8"},
    "仓管": {"U8"},
    "生产": {"U8"},
}

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

TABLE_MARKINGS: dict = {}

PURPOSE_REQUIRED = {
    "FIN": {"授信审核", "财务对账", "风控", "审批"},
}

ROW_POLICIES = {
    "inventory": {"role": "仓管", "column": "warehouse_id", "attr": "warehouse_id"},
}

ACTION_PERMISSIONS = {
    "adjust_safety_stock": {"roles": {"采购", "管理层", "管理员"}, "markings": set()},
    "create_purchase_requisition": {"roles": {"采购", "管理层", "管理员"}, "markings": set()},
    "create_delivery": {"roles": {"仓管", "管理层", "管理员"}, "markings": set()},
}


def _clean_lookup(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be non-empty unpadded text")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field} contains control characters")
    return value


@dataclass
class User:
    """Access subject: role + PBAC purpose + row-policy attributes."""
    name: str
    role: str = "仓管"
    purpose: str = ""
    attrs: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = _clean_lookup(self.name, field="user name")
        self.role = _clean_lookup(self.role, field="user role")
        if self.role not in ROLES:
            raise ValueError(f"unsupported user role: {self.role}")
        if self.purpose:
            self.purpose = _clean_lookup(self.purpose, field="user purpose")
        if not isinstance(self.attrs, dict):
            raise ValueError("user attrs must be a mapping")
        self.attrs = dict(self.attrs)

    @property
    def markings(self) -> set:
        return set(ROLE_MARKINGS.get(self.role, set()))


def column_markings(table: str, column: str) -> list:
    table = _clean_lookup(table, field="table")
    column = _clean_lookup(column, field="column")
    return list(COLUMN_MARKINGS.get((table, column), []))


def table_markings(table: str) -> list:
    table = _clean_lookup(table, field="table")
    return list(TABLE_MARKINGS.get(table, []))
