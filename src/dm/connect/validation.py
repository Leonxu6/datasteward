"""连接配置的轻量规范化与前置校验。"""


def normalize_required_text(value, *, field_name: str) -> str:
    """要求配置值为非空字符串，并拒绝容易隐藏 typo 的首尾空白。"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串: {value!r}")
    if not value:
        raise ValueError(f"{field_name} 不能为空")
    if value != value.strip():
        raise ValueError(f"{field_name} 不能包含首尾空白: {value!r}")
    return value
