"""权限层（对标 Palantir 两层安全：强制 Markings AND 自主角色 + 行/列 + 写回权限独立）。

见 docs/palantir/05-权限与Markings.md。
"""
from dm.security.model import (
    ACTION_PERMISSIONS,
    COLUMN_MARKINGS,
    MARKINGS,
    PURPOSE_REQUIRED,
    ROLE_MARKINGS,
    ROLES,
    ROW_POLICIES,
    TABLE_MARKINGS,
    User,
    column_markings,
    table_markings,
)
from dm.security.policy import (
    apply_mask,
    apply_row_policies,
    can_execute_action,
    can_read_table,
    effective_user_markings,
    enforce_query,
    purpose_ok,
    row_filter,
    user_from_env,
)

__all__ = [
    "ACTION_PERMISSIONS", "COLUMN_MARKINGS", "MARKINGS", "PURPOSE_REQUIRED", "ROLE_MARKINGS",
    "ROLES", "ROW_POLICIES", "TABLE_MARKINGS", "User", "column_markings", "table_markings",
    "apply_mask", "apply_row_policies", "can_execute_action", "can_read_table",
    "effective_user_markings", "enforce_query", "purpose_ok", "row_filter", "user_from_env",
]
