"""Ontology 语义层模型 + 从 schema.py 派生的本体注册表。

对标 Palantir Ontology 的"名词层"（语义层）：
- **Object Type** ← schema.py 的每张业务表（落实 Palantir "1 datasource ↔ 1 object type"）
- **Property**    ← 表的列（强类型 base type + 中文显示名 + 主键标记）
- **Link Type**   ← 表的外键（many-to-one：子→父；自引用亦可）

设计取舍（见 docs/palantir/03-Ontology本体层.md）：
- **单一真相源仍是 `schema.py`**；本体层是它的"语义超集"，派生而来，不另立事实。
- 主键用**业务 ID（确定性）**而非行号——满足 Palantir "主键须 deterministic 否则重建丢用户编辑"。
- 复合主键（如 purchase_order = po_id+line_no）：外键按"被引用表主键首列"对齐（与 DEVLOG 坑13 一致）。

"动词层"（Action Type / Function，治理化写回）见 `ontology/actions.py`（Phase 1 治理切片）。
"""
from dataclasses import dataclass, field
from typing import Optional

from dm.schema import TABLES

BASE_TYPE_MAP = {
    "VARCHAR": "String", "TEXT": "String", "CHAR": "String",
    "INTEGER": "Integer", "INT": "Integer", "BIGINT": "Long", "SMALLINT": "Short",
    "DOUBLE": "Double", "FLOAT": "Float", "DECIMAL": "Decimal",
    "BOOLEAN": "Boolean", "DATE": "Date", "TIMESTAMP": "Timestamp", "DATETIME": "Timestamp",
}

_GROUPS = {
    "主数据": {"company_org", "department", "employee", "unit", "material_category",
             "material", "unit_conversion", "supplier", "customer", "dictionary",
             "warehouse", "storage_location"},
    "库存": {"inventory"},
    "单据": {"purchase_order", "purchase_arrival", "sales_order",
            "delivery_note", "production_order", "production_material_req"},
}


def _clean_model_name(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} must be clean non-empty text")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field_name} contains control characters")
    return value


def to_pascal(name: str) -> str:
    """purchase_order -> PurchaseOrder（Object Type 的 API name 规范）。"""
    name = _clean_model_name(name, field_name="object source name")
    return "".join(p[:1].upper() + p[1:] for p in name.split("_") if p)


def to_camel(col: str) -> str:
    """unit_price -> unitPrice（Property / Link 的 API name 规范）。"""
    col = _clean_model_name(col, field_name="property source name")
    parts = [p for p in col.split("_") if p]
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _group_of(name: str) -> str:
    for g, s in _GROUPS.items():
        if name in s:
            return g
    return "其他"


@dataclass
class Property:
    """对象属性（对标 Palantir Property）。"""
    api_name: str
    column: str
    base_type: str
    display_name: str
    is_primary_key: bool = False
    fk_to: Optional[str] = None


@dataclass
class LinkType:
    """链接类型（对标 Palantir Link Type；v0 由外键派生 many-to-one）。"""
    api_name: str
    from_object: str
    to_object: str
    cardinality: str
    from_property: str
    to_property: str
    display_name: str


@dataclass
class ObjectType:
    """对象类型（对标 Palantir Object Type；1 datasource ↔ 1 object type）。"""
    api_name: str
    table: str
    display_name: str
    plural_display_name: str
    description: str
    primary_key: list
    title_property: str
    group: str
    status: str = "active"
    properties: list = field(default_factory=list)
    links: list = field(default_factory=list)

    def prop(self, api_or_col: str) -> Optional[Property]:
        for p in self.properties:
            if p.api_name == api_or_col or p.column == api_or_col:
                return p
        return None


def _build() -> dict:
    """从 schema.py 派生对象类型注册表（含属性与外键链接）。"""
    obj: dict = {}
    for t in TABLES:
        pk_cols = t["pk"].split("+")
        fkmap = {c: tgt for c, tgt in t["fks"]}
        props = [
            Property(
                api_name=to_camel(col), column=col,
                base_type=BASE_TYPE_MAP.get(sqltype.upper(), "String"),
                display_name=cn, is_primary_key=(col in pk_cols),
                fk_to=fkmap.get(col),
            )
            for col, sqltype, cn in t["columns"]
        ]
        title = "name" if any(c[0] == "name" for c in t["columns"]) else pk_cols[0]
        obj[t["name"]] = ObjectType(
            api_name=to_pascal(t["name"]), table=t["name"],
            display_name=t["cn"], plural_display_name=t["cn"], description=t["desc"],
            primary_key=pk_cols, title_property=title, group=_group_of(t["name"]),
            properties=props,
        )
    for t in TABLES:
        src = obj[t["name"]]
        for col, tgt in t["fks"]:
            tgt_ot = obj.get(tgt)
            if tgt_ot is None:
                continue
            rel = to_camel(col[:-3]) if col.endswith("_id") else to_camel(col)
            src.links.append(LinkType(
                api_name=rel or to_camel(col),
                from_object=src.api_name, to_object=tgt_ot.api_name,
                cardinality="many-to-one",
                from_property=col, to_property=tgt_ot.primary_key[0],
                display_name=f"{src.display_name} → {tgt_ot.display_name}",
            ))
    return obj


ONTOLOGY: dict = _build()


def object_types() -> list:
    """返回全部对象类型。"""
    return list(ONTOLOGY.values())


def get_object_type(name_or_api: str) -> Optional[ObjectType]:
    """按表英文名或 API name（PascalCase）查对象类型。"""
    name_or_api = _clean_model_name(name_or_api, field_name="object type name")
    if name_or_api in ONTOLOGY:
        return ONTOLOGY[name_or_api]
    for ot in ONTOLOGY.values():
        if ot.api_name == name_or_api:
            return ot
    return None


def incoming_links(api_name: str) -> list:
    """返回所有指向该对象类型的链接（其它对象 → 本对象；用于 get_links 的反向遍历）。"""
    ot = get_object_type(api_name)
    if not ot:
        return []
    out = []
    for other in ONTOLOGY.values():
        for lk in other.links:
            if lk.to_object == ot.api_name:
                out.append(lk)
    return out
