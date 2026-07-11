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

# SQL 类型 → Palantir base type（对齐 docs/palantir/03 的 base type 全枚举）
BASE_TYPE_MAP = {
    "VARCHAR": "String", "TEXT": "String", "CHAR": "String",
    "INTEGER": "Integer", "INT": "Integer", "BIGINT": "Long", "SMALLINT": "Short",
    "DOUBLE": "Double", "FLOAT": "Float", "DECIMAL": "Decimal",
    "BOOLEAN": "Boolean", "DATE": "Date", "TIMESTAMP": "Timestamp", "DATETIME": "Timestamp",
}

# 对象分组（≈ Palantir groups；供 Object Explorer 归类）
_GROUPS = {
    "主数据": {"company_org", "department", "employee", "unit", "material_category",
             "material", "unit_conversion", "supplier", "customer", "dictionary",
             "warehouse", "storage_location"},
    "库存": {"inventory"},
    "单据": {"purchase_order", "purchase_arrival", "sales_order",
            "delivery_note", "production_order", "production_material_req"},
}


def to_pascal(name: str) -> str:
    """purchase_order -> PurchaseOrder（Object Type 的 API name 规范）。"""
    return "".join(p[:1].upper() + p[1:] for p in name.split("_") if p)


def to_camel(col: str) -> str:
    """unit_price -> unitPrice（Property / Link 的 API name 规范）。"""
    parts = [p for p in col.split("_") if p]
    if not parts:
        return col
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _group_of(name: str) -> str:
    for g, s in _GROUPS.items():
        if name in s:
            return g
    return "其他"


@dataclass
class Property:
    """对象属性（对标 Palantir Property）。"""
    api_name: str                 # camelCase 语义名
    column: str                   # 背书列名（原始，用于取数）
    base_type: str                # Palantir base type
    display_name: str             # 中文显示名
    is_primary_key: bool = False
    fk_to: Optional[str] = None   # 外键指向的表英文名（用于派生 Link）


@dataclass
class LinkType:
    """链接类型（对标 Palantir Link Type；v0 由外键派生 many-to-one）。"""
    api_name: str                 # 关系名（camelCase）
    from_object: str              # 源对象 API name（PascalCase）
    to_object: str                # 目标对象 API name
    cardinality: str              # many-to-one / one-to-one / many-to-many
    from_property: str            # 源侧外键列（原始列名）
    to_property: str              # 目标侧主键列（原始列名）
    display_name: str             # 中文关系描述


@dataclass
class ObjectType:
    """对象类型（对标 Palantir Object Type；1 datasource ↔ 1 object type）。"""
    api_name: str                 # PascalCase
    table: str                    # 背书数据源（StarRocks/PG 表名）
    display_name: str             # 中文名
    plural_display_name: str
    description: str
    primary_key: list             # 列名列表（支持复合）
    title_property: str           # 展示用属性（列名）
    group: str
    status: str = "active"        # active / experimental / deprecated
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
        # title 属性：优先名为 name 的列，否则取主键首列
        title = "name" if any(c[0] == "name" for c in t["columns"]) else pk_cols[0]
        obj[t["name"]] = ObjectType(
            api_name=to_pascal(t["name"]), table=t["name"],
            display_name=t["cn"], plural_display_name=t["cn"], description=t["desc"],
            primary_key=pk_cols, title_property=title, group=_group_of(t["name"]),
            properties=props,
        )
    # 派生链接：每个外键 → many-to-one（子对象 → 父对象）；自引用亦建
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


# 本体注册表（进程级构建一次；派生自 schema.py，无副作用、无需 DB）
ONTOLOGY: dict = _build()


def object_types() -> list:
    """返回全部对象类型。"""
    return list(ONTOLOGY.values())


def get_object_type(name_or_api: str) -> Optional[ObjectType]:
    """按表英文名或 API name（PascalCase）查对象类型。"""
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
