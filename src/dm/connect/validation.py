"""连接配置的轻量规范化与前置校验。"""
import re

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


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
    """校验环境变量引用名，同时兼容外部 secret stores 常见的点号/连字符键名。"""
    value = normalize_required_text(value, field_name=field_name)
    if not _ENV_NAME.fullmatch(value):
        raise ValueError(f"{field_name} 必须是可移植环境引用名: {value!r}")
    return value


def normalize_identifier(value, *, field_name: str) -> str:
    """校验数据库标识符文本；允许空格、连字符和 Unicode，由各驱动负责安全引用。"""
    return normalize_required_text(value, field_name=field_name)
