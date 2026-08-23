"""Validation helpers shared by external messaging channels."""
from __future__ import annotations

import math
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _clean_field_name(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("field_name 必须是非空且无首尾空白的字符串")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("field_name 不能包含控制字符")
    return value


def _positive_limit(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} 必须是正整数")
    return value


def _unsafe_message_control(ch: str) -> bool:
    code = ord(ch)
    return code == 127 or (code < 32 and ch not in "\n\r\t")


def normalize_message_text(value, *, field_name: str = "message", max_length: int = 20_000) -> str:
    """Return bounded text suitable for sending to an external channel."""
    field_name = _clean_field_name(field_name)
    max_length = _positive_limit(max_length, field="max_length")
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串")
    if not value or not value.strip():
        raise ValueError(f"{field_name} 不能为空")
    if len(value) > max_length:
        raise ValueError(f"{field_name} 不能超过 {max_length} 个字符")
    if any(_unsafe_message_control(ch) for ch in value):
        raise ValueError(f"{field_name} 不能包含不安全控制字符")
    return value


def normalize_webhook_url(value, *, field_name: str = "webhook") -> str:
    """Require a credential-free HTTPS webhook with a concrete hostname."""
    field_name = _clean_field_name(field_name)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} 必须是非空且无首尾空白的字符串")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field_name} 不能包含控制字符")
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field_name} URL 格式无效") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError(f"{field_name} 必须是带主机名的 https:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} 不能内嵌用户名或密码")
    return value


def append_query_params(url: str, **params: object) -> str:
    """Merge query parameters without assuming the webhook already contains `?`."""
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.extend((key, str(value)) for key, value in params.items())
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def normalize_positive_int(value, *, field_name: str, default: int, maximum: int) -> int:
    """Parse a bounded positive integer from code or environment-style strings."""
    value = default if value is None else value
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是正整数")
    if isinstance(value, str):
        if not value or value != value.strip() or not value.isascii() or not value.isdecimal():
            raise ValueError(f"{field_name} 必须是正整数")
        result = int(value)
    elif isinstance(value, int):
        result = value
    else:
        raise ValueError(f"{field_name} 必须是正整数")
    if result <= 0 or result > maximum:
        raise ValueError(f"{field_name} 必须在 1-{maximum} 范围内")
    return result


def normalize_nonnegative_int(value, *, field_name: str, default: int, maximum: int) -> int:
    """Parse a bounded integer that may be zero, useful for disabling queue capacity."""
    value = default if value is None else value
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是非负整数")
    if isinstance(value, str):
        if not value or value != value.strip() or not value.isascii() or not value.isdecimal():
            raise ValueError(f"{field_name} 必须是非负整数")
        result = int(value)
    elif isinstance(value, int):
        result = value
    else:
        raise ValueError(f"{field_name} 必须是非负整数")
    if result < 0 or result > maximum:
        raise ValueError(f"{field_name} 必须在 0-{maximum} 范围内")
    return result


def normalize_positive_float(value, *, field_name: str, default: float, maximum: float) -> float:
    """Parse a finite positive float with an explicit upper bound."""
    value = default if value is None else value
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是正数")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是正数") from exc
    if not math.isfinite(result) or result <= 0 or result > maximum:
        raise ValueError(f"{field_name} 必须在 (0, {maximum:g}] 范围内")
    return result
