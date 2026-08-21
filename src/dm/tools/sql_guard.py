"""SQL 白名单守卫：只放行单条 SELECT/WITH（连接 read_only 之外的第二道保险）。

从原 mcp_server 拆出：_FORBIDDEN 关键字、涉表识别、只读校验。
"""
import re

from dm.schema import business_table_names

# 写/DDL/危险关键字（read_only 连接已兜底，这里再拦一层并给出清晰报错）
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|pragma|truncate|"
    r"replace|export|import|install|load|set|reset|call|merge|vacuum|explain|show)\b", re.I)


def _mask_literals_and_comments(sql: str) -> tuple[str, str | None]:
    """Mask quoted text/comments while preserving whitespace and token positions."""
    out = list(sql)
    i = 0
    state = "normal"
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""

        if state == "normal":
            if ch == "'":
                out[i] = " "
                state = "single"
            elif ch == '"':
                out[i] = " "
                state = "double"
            elif ch == "-" and nxt == "-":
                out[i] = out[i + 1] = " "
                i += 1
                state = "line_comment"
            elif ch == "/" and nxt == "*":
                out[i] = out[i + 1] = " "
                i += 1
                state = "block_comment"
        elif state == "single":
            if ch == "'" and nxt == "'":
                out[i] = out[i + 1] = " "
                i += 1
            elif ch == "'":
                out[i] = " "
                state = "normal"
            elif ch != "\n":
                out[i] = " "
        elif state == "double":
            if ch == '"' and nxt == '"':
                out[i] = out[i + 1] = " "
                i += 1
            elif ch == '"':
                out[i] = " "
                state = "normal"
            elif ch != "\n":
                out[i] = " "
        elif state == "line_comment":
            if ch == "\n":
                state = "normal"
            else:
                out[i] = " "
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                out[i] = out[i + 1] = " "
                i += 1
                state = "normal"
            elif ch != "\n":
                out[i] = " "
        i += 1

    if state in {"single", "double", "block_comment"}:
        return "".join(out), "ERROR: SQL 中存在未闭合的引号或注释。"
    return "".join(out), None


def tables_in(sql: str) -> list:
    """识别 SQL 里真实引用的业务表，忽略字符串字面量和注释。"""
    if not isinstance(sql, str):
        return []
    masked, _ = _mask_literals_and_comments(sql)
    low = masked.lower()
    return [n for n in business_table_names() if re.search(r"\b" + re.escape(n) + r"\b", low)]


def validate_readonly(sql: str) -> tuple:
    """只读校验。返回 (clean_sql, err)：err 非空表示拒绝原因（对外可见的中文报错）。"""
    if not isinstance(sql, str):
        return "", "ERROR: SQL 必须是字符串。"
    clean = sql.strip()
    if not clean:
        return clean, "ERROR: SQL 不能为空。"
    if clean.endswith(";"):
        clean = clean[:-1].rstrip()

    masked, mask_error = _mask_literals_and_comments(clean)
    if mask_error:
        return clean, mask_error
    if ";" in masked:
        return clean, "ERROR: 只允许单条查询语句（不要用分号拼接多条）。"
    if not re.match(r"(?is)^\s*(select|with)\b", masked):
        return clean, "ERROR: 只允许 SELECT/WITH 查询。"
    if FORBIDDEN.search(masked):
        return clean, "ERROR: 检测到写/DDL 关键字，已拒绝（连接器只读）。"
    return clean, None
