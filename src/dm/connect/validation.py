"""连接配置的轻量规范化与前置校验。"""


def normalize_required_text(value, *, field_name: str) -> str:
    """要求配置值为非空字符串，并拒绝容易隐藏 typo 的空白和控制字符。"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串: {value!r}")
    if not value:
        raise ValueError(f"{field_name} 不能为空")
    if value != value.strip():
        raise ValueError(f"{field_name} 不能包含首尾空白: {value!r}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field_name} 不能包含控制字符: {value!r}")
    return value


def normalize_env_name(value, *, field_name: str = "credential_env") -> str:
    """校验环境变量引用名，避免无效键在 ``os.environ`` 访问时才以底层异常失败。"""
    value = normalize_required_text(value, field_name=field_name)
    if "=" in value:
        raise ValueError(f"{field_name} 不能包含 '=': {value!r}")
    return value


def normalize_identifier(value, *, field_name: str) -> str:
    """校验数据库标识符文本；允许空格、连字符和 Unicode，由各驱动负责安全引用。"""
    return normalize_required_text(value, field_name=field_name)
