"""权限判定引擎（在 MCP 连接器内强制执行）。

读路径（run_sql）判定 `enforce_query`：
1. **对象/表级**：表上的 Marking 用户须全有，否则拒（discovery restriction）。
2. **属性/列级**：查询**显式引用**了缺权限的列 → 拒（清晰"被挡"）；
   `SELECT *` 情形则允许但把缺权限列在结果里**屏蔽为 null**（对标 Palantir property policy 的 null 语义）。
写路径（Action）判定 `can_execute_action`：**独立于读权限**的执行门。
全程返回决策供 MCP 层写审计（authorizationCheck，allow/deny + 命中 Marking）。
"""
import os
import re

from dm.security.model import (
    ACTION_PERMISSIONS,
    COLUMN_MARKINGS,
    PURPOSE_REQUIRED,
    ROW_POLICIES,
    User,
    table_markings,
)


def user_from_env() -> User:
    """从环境变量构建当前用户（由 agent/通道经 mcp-config 注入；默认最小权限 仓管）。"""
    attrs = {}
    wh = os.environ.get("DM_WAREHOUSE")
    if wh:
        attrs["warehouse_id"] = wh   # 行级策略：仓管的管辖仓库
    return User(
        name=os.environ.get("DM_USER", "anonymous"),
        role=os.environ.get("DM_ROLE", "仓管"),
        purpose=os.environ.get("DM_PURPOSE", ""),
        attrs=attrs,
    )


def purpose_ok(marking: str, purpose: str) -> bool:
    """PBAC：访问带该 Marking 的数据，本次目的是否被允许。未列入 PURPOSE_REQUIRED 的不设限。"""
    allowed = PURPOSE_REQUIRED.get(marking)
    return True if not allowed else (purpose in allowed)


def effective_user_markings(user: User) -> set:
    """本次访问**实际生效**的 Marking = 角色 Marking ∩ 满足 PBAC 目的约束的那些。"""
    return {m for m in user.markings if purpose_ok(m, user.purpose)}


def _table_required_markings(table: str) -> set:
    """表的对象级强制 Marking = 显式表标 + 沿血缘传播来的有效 Marking（安全随数据跑）。"""
    marks = set(table_markings(table))
    try:  # 惰性导入，避免 security→lineage→datasets→ontology 的导入环
        from dm.pipeline.lineage import effective_markings
        marks |= set(effective_markings(table))
    except Exception:  # noqa: BLE001
        pass
    return marks


def _disallowed_columns(um: set, tables: list) -> list:
    """这些表中，按有效 Marking `um` 无权访问的列 → [(table, col, markings)]。"""
    out = []
    for (t, col), marks in COLUMN_MARKINGS.items():
        if t in tables and not set(marks) <= um:
            out.append((t, col, marks))
    return out


def enforce_query(user: User, sql: str, tables_touched: list) -> dict:
    """读查询的权限判定。返回 {allow, reason, mask_columns, hit_markings}。"""
    um = effective_user_markings(user)
    low = sql.lower()

    # 1) 对象/表级强制 Marking（含沿血缘传播）：缺则整表不可见
    for t in tables_touched:
        need = _table_required_markings(t)
        if not need <= um:
            miss = sorted(need - um)
            return {"allow": False, "mask_columns": [], "hit_markings": miss,
                    "reason": f"缺少 Marking {miss}，无权访问表『{t}』（角色 {user.role}"
                              + (f"/目的『{user.purpose}』" if user.purpose else "") + "）"}

    # 2) 列级：按有效 Marking 求缺权限列
    disallowed = _disallowed_columns(um, tables_touched)

    # 2a) 显式引用了缺权限列 → 直接拒（区分"角色无 marking"与"PBAC 目的不满足"）
    for t, col, marks in disallowed:
        if re.search(r"\b" + re.escape(col) + r"\b", low):
            role_has = set(marks) <= user.markings
            extra = "（该字段受 PBAC 约束，当前访问目的不满足）" if role_has else ""
            return {"allow": False, "mask_columns": [c for _, c, _ in disallowed],
                    "hit_markings": marks,
                    "reason": f"需要 Marking {marks}{extra} 才能访问『{t}.{col}』（角色 {user.role}）"}

    # 3) 允许；SELECT * 情形把缺权限列在结果里屏蔽为 null
    return {"allow": True, "mask_columns": [c for _, c, _ in disallowed],
            "hit_markings": [], "reason": ""}


def apply_mask(columns: list, rows: list, mask_columns: list) -> tuple:
    """把结果里 mask_columns 命中的列值屏蔽为 None（property policy 的 null 语义）。
    返回 (rows, masked_present)：masked_present 为实际出现在结果里的被屏蔽列名。"""
    mset = set(mask_columns)
    idx = [i for i, c in enumerate(columns) if c in mset]
    if not idx:
        return rows, []
    masked = [columns[i] for i in idx]
    out = []
    for r in rows:
        rr = list(r)
        for i in idx:
            rr[i] = None
        out.append(tuple(rr))
    return out, masked


def can_read_table(user: User, table: str) -> bool:
    """对象/表级可见性（含沿血缘传播的 Marking；供 ontology OSDK 用）。"""
    return _table_required_markings(table) <= effective_user_markings(user)


def row_filter(user: User, table: str):
    """行级对象策略（Palantir object policy = 行级）：
    返回 (column, value) 表示该用户对本表"只可见 column==value 的行"；无策略则 None。
    与列级属性策略叠加即"单元格级"。"""
    pol = ROW_POLICIES.get(table)
    if not pol or user.role != pol["role"]:
        return None
    val = user.attrs.get(pol["attr"])
    return (pol["column"], val) if val else None


def apply_row_policies(user: User, sql: str, tables_touched: list) -> str:
    """对 run_sql 施加行级策略：把受限表的 FROM/JOIN 引用替换为过滤子查询
    （别名保留为表名，后续列引用不变）。这样原始 SQL 的 join/列/where 都不动，仅收窄可见行。"""
    out = sql
    for t in tables_touched:
        rf = row_filter(user, t)
        if not rf:
            continue
        col, val = rf
        val_esc = str(val).replace("'", "''")
        sub = f"(SELECT * FROM `{t}` WHERE `{col}`='{val_esc}') {t}"
        out = re.sub(r"(?i)(\bfrom\b|\bjoin\b)\s+`?" + re.escape(t) + r"`?(?!\w)", r"\1 " + sub, out)
    return out


def can_execute_action(user: User, action: str) -> tuple:
    """写回 Action 的执行判定（**独立于读权限**）。返回 (allow, reason)。"""
    perm = ACTION_PERMISSIONS.get(action)
    if not perm:
        return False, f"未知 Action：{action}"
    if user.role not in perm["roles"]:
        return False, f"角色『{user.role}』无权执行『{action}』（需 {sorted(perm['roles'])} 之一）"
    miss = set(perm["markings"]) - effective_user_markings(user)
    if miss:
        return False, f"缺少 Marking {sorted(miss)}，无权执行『{action}』"
    return True, "ok"
