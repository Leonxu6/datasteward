"""Ontology 本体层：把 schema.py 的 19 张表提升为 Palantir 式对象/属性/链接语义层。

- 语义层（本模块）：ObjectType / Property / LinkType，派生自 schema.py（单一真相源不变）。
- 读 API（osdk）：list_objects / get_object / get_links —— 对标 Palantir OSDK。
- 动词层（actions）：治理化写回 Action，见 ontology/actions.py（Phase 1 治理切片）。

见 docs/palantir/03-Ontology本体层.md。
"""
from dm.ontology.model import (
    BASE_TYPE_MAP,
    LinkType,
    ObjectType,
    Property,
    ONTOLOGY,
    get_object_type,
    incoming_links,
    object_types,
    to_camel,
    to_pascal,
)
from dm.ontology.osdk import get_links, get_object, list_objects
from dm.ontology.actions import (
    ACTION_TYPES,
    action_history,
    approve_action,
    execute_action,
    list_action_types,
    pending_actions,
    rollback_action,
)

__all__ = [
    "BASE_TYPE_MAP", "LinkType", "ObjectType", "Property", "ONTOLOGY",
    "get_object_type", "incoming_links", "object_types", "to_camel", "to_pascal",
    "get_links", "get_object", "list_objects",
    "ACTION_TYPES", "action_history", "approve_action", "execute_action",
    "list_action_types", "pending_actions", "rollback_action",
]
