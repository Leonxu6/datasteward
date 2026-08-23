"""SQL 白名单守卫：只放行单条 SELECT/WITH（连接 read_only 之外的第二道保险）。

从原 mcp_server 拆出：_FORBIDDEN 关键字、涉表识别、只读校验。
"""
import re

from dm.schema import business_table_names

MAX_SQL_CHARS = 100_000

# 写/DDL/危险关键字（read_only 连接已兜底，这里再拦一层并给出清晰报错）
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|pragma|truncate|"
    r"replace|export|import|install|load|set|reset|call|merge|vacuum|explain|show)\b", re.I)


def _require_sql_text(sql: object) -> str:
    if not isinstance(sql, str):
        raise TypeError("sql must be a string")
    return sql


def tables_in(sql: str) -> list:
    """识别 SQL 里引用了哪些业务表（按词边界匹配表名）。"""
    sql = _require_sql_text(sql)
    low = sql.lower()
    return [n for n in business_table_names() if re.search(r"\b" + re.escape(n) + r"\b", low)]


def validate_readonly(sql: str) -> tuple:
    """只读校验。返回 (clean_sql, err)：err 非空表示拒绝原因（对外可见的中文报错）。"""
    try:
        sql = _require_sql_text(sql)
    except TypeError:
        return "", "ERROR: SQL 必须是字符串。"
    if len(sql) > MAX_SQL_CHARS:
        return "", f"ERROR: SQL 过长，最多允许 {MAX_SQL_CHARS} 个字符。"
    clean = sql.strip().rstrip(";").strip()
    if ";" in clean:
        return clean, "ERROR: 只允许单条查询语句（不要用分号拼接多条）。"
    if not re.match(r"(?is)^\s*(select|with)\b", clean):
        return clean, "ERROR: 只允许 SELECT/WITH 查询。"
    if FORBIDDEN.search(clean):
        return clean, "ERROR: 检测到写/DDL 关键字，已拒绝（连接器只读）。"
    return clean, None
