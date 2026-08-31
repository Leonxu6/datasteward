"""Normalization helpers for user-controlled principal metadata."""
from __future__ import annotations

_MAX_FIELD_NAME = 80


def _field_name(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("field_name must be non-empty unpadded text")
    if len(value) > _MAX_FIELD_NAME:
        raise ValueError(f"field_name must be at most {_MAX_FIELD_NAME} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("field_name must not contain control characters")
    return value


def _max_length(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("max_length must be a positive integer")
    return value


def normalize_identity_text(
    value,
    *,
    field_name: str,
    default: str = "",
    max_length: int = 200,
    allow_empty: bool = True,
) -> str:
    """Normalize audit/PBAC identity text without silently trimming malformed input."""
    field_name = _field_name(field_name)
    max_length = _max_length(max_length)
    if not isinstance(allow_empty, bool):
        raise ValueError("allow_empty must be boolean")
    if value is None:
        value = default
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串")
    if value != value.strip():
        raise ValueError(f"{field_name} 不能包含首尾空白")
    if not value and not allow_empty:
        raise ValueError(f"{field_name} 不能为空")
    if len(value) > max_length:
        raise ValueError(f"{field_name} 不能超过 {max_length} 个字符")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field_name} 不能包含控制字符")
    return value


def normalize_channel(value, *, default: str = "mcp") -> str:
    """Normalize a short machine-readable channel label."""
    result = normalize_identity_text(
        value,
        field_name="channel",
        default=default,
        max_length=40,
        allow_empty=False,
    )
    if not all(ch.isalnum() or ch in "_-" for ch in result):
        raise ValueError("channel 只能包含字母、数字、下划线和连字符")
    return result
