"""Typed environment parsing used by process-wide DataSteward configuration."""
from __future__ import annotations

import math
import os
from urllib.parse import urlsplit

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} 必须是正整数")
    return value


def _integer_bound(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} 必须是整数")
    return value


def _finite_bound(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} 必须是数字")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} 必须是有限数字")
    return result


def env_text(name: str, default: str, *, allow_empty: bool = False, max_length: int = 1000) -> str:
    if not isinstance(allow_empty, bool):
        raise ValueError("allow_empty 必须是布尔值")
    max_length = _positive_int(max_length, field="max_length")
    raw = os.environ.get(name)
    value = default if raw is None else raw
    if not isinstance(value, str):
        raise ValueError(f"{name} 必须是字符串")
    if value != value.strip():
        raise ValueError(f"{name} 不能包含首尾空白")
    if not value and not allow_empty:
        raise ValueError(f"{name} 不能为空")
    if len(value) > max_length:
        raise ValueError(f"{name} 不能超过 {max_length} 个字符")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{name} 不能包含控制字符")
    return value


def env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    minimum = _integer_bound(minimum, field="minimum")
    maximum = _integer_bound(maximum, field="maximum")
    if minimum > maximum:
        raise ValueError("minimum 不能大于 maximum")
    raw = os.environ.get(name)
    if raw is None:
        if isinstance(default, bool) or not isinstance(default, int):
            raise ValueError(f"{name} 默认值必须是整数")
        result = default
    else:
        if not raw or raw != raw.strip() or not raw.isascii() or not raw.isdecimal():
            raise ValueError(f"{name} 必须是整数")
        result = int(raw)
    if result < minimum or result > maximum:
        raise ValueError(f"{name} 必须在 {minimum}-{maximum} 范围内")
    return result


def env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    minimum = _finite_bound(minimum, field="minimum")
    maximum = _finite_bound(maximum, field="maximum")
    if minimum > maximum:
        raise ValueError("minimum 不能大于 maximum")
    raw = os.environ.get(name)
    if raw is None:
        if isinstance(default, bool) or not isinstance(default, (int, float)):
            raise ValueError(f"{name} 默认值必须是数字")
        result = float(default)
    else:
        try:
            result = float(raw)
        except ValueError as exc:
            raise ValueError(f"{name} 必须是数字") from exc
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise ValueError(f"{name} 必须在 {minimum:g}-{maximum:g} 范围内")
    return result


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        if not isinstance(default, bool):
            raise ValueError(f"{name} 默认值必须是布尔值")
        return default
    if raw != raw.strip() or not raw:
        raise ValueError(f"{name} 必须是布尔值")
    normalized = raw.lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ValueError(f"{name} 必须是 true/false, yes/no, on/off 或 1/0")


def env_http_url(name: str, default: str) -> str:
    value = env_text(name, default, max_length=2048)
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError(f"{name} URL 格式无效") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{name} 必须是带主机名的 http(s) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{name} 不能在 URL 中内嵌凭据")
    return value.rstrip("/")
