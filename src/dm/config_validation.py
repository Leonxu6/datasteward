"""Typed environment parsing used by process-wide DataSteward configuration."""
from __future__ import annotations

import ipaddress
import math
import os
import re
import string
from urllib.parse import urlsplit

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FLOAT_TEXT = re.compile(r"^-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")
_MAX_ENV_NAME = 128
_MAX_NUMERIC_TEXT = 128
_MAX_TEXT_LENGTH = 100_000
_MAX_DNS_NAME = 253
_MAX_DNS_LABEL = 63
_HEX_DIGITS = frozenset(string.hexdigits)
_BIDI_CONTROLS = {
    "\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
}


def _env_name(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("环境变量名必须是非空且无首尾空白的字符串")
    if len(value) > _MAX_ENV_NAME:
        raise ValueError(f"环境变量名不能超过 {_MAX_ENV_NAME} 个字符")
    if not _ENV_NAME.fullmatch(value):
        raise ValueError("环境变量名只能包含字母、数字和下划线，且不能以数字开头")
    return value


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
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{field} 必须是有限数字") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} 必须是有限数字")
    return result


def _numeric_address_token(label: str) -> bool:
    if label.isascii() and label.isdigit():
        return True
    lower = label.lower()
    return lower.startswith("0x") and len(lower) > 2 and all(ch in _HEX_DIGITS for ch in lower[2:])


def _valid_hostname(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass
    if hostname.lower() == "localhost":
        return True
    if not hostname.isascii() or len(hostname) > _MAX_DNS_NAME:
        return False
    if hostname.startswith(".") or hostname.endswith(".") or ".." in hostname:
        return False
    labels = hostname.split(".")
    if labels and all(_numeric_address_token(label) for label in labels):
        return False
    for label in labels:
        if not label or len(label) > _MAX_DNS_LABEL or label.startswith("-") or label.endswith("-"):
            return False
        if not all(ch.isalnum() or ch in {"-", "_"} for ch in label):
            return False
    return True


def env_text(name: str, default: str, *, allow_empty: bool = False, max_length: int = 1000) -> str:
    name = _env_name(name)
    if not isinstance(allow_empty, bool):
        raise ValueError("allow_empty 必须是布尔值")
    max_length = _positive_int(max_length, field="max_length")
    if max_length > _MAX_TEXT_LENGTH:
        raise ValueError(f"max_length 不能超过 {_MAX_TEXT_LENGTH}")
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
    if any(ord(ch) < 32 or ord(ch) == 127 or ch in _BIDI_CONTROLS for ch in value):
        raise ValueError(f"{name} 不能包含控制字符")
    return value


def env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    name = _env_name(name)
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
        if len(raw) > _MAX_NUMERIC_TEXT:
            raise ValueError(f"{name} 数字文本过长")
        digits = raw[1:] if raw.startswith("-") else raw
        if not raw or raw != raw.strip() or raw.startswith("+") or not digits or not digits.isascii() or not digits.isdecimal():
            raise ValueError(f"{name} 必须是整数")
        try:
            result = int(raw)
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"{name} 必须是整数") from exc
    if result < minimum or result > maximum:
        raise ValueError(f"{name} 必须在 {minimum}-{maximum} 范围内")
    return result


def env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    name = _env_name(name)
    minimum = _finite_bound(minimum, field="minimum")
    maximum = _finite_bound(maximum, field="maximum")
    if minimum > maximum:
        raise ValueError("minimum 不能大于 maximum")
    raw = os.environ.get(name)
    if raw is None:
        if isinstance(default, bool) or not isinstance(default, (int, float)):
            raise ValueError(f"{name} 默认值必须是数字")
        try:
            result = float(default)
        except OverflowError as exc:
            raise ValueError(f"{name} 默认值必须是有限数字") from exc
    else:
        if len(raw) > _MAX_NUMERIC_TEXT:
            raise ValueError(f"{name} 数字文本过长")
        if not raw or raw != raw.strip() or not raw.isascii() or not _FLOAT_TEXT.fullmatch(raw):
            raise ValueError(f"{name} 必须是数字")
        try:
            result = float(raw)
        except (OverflowError, ValueError) as exc:
            raise ValueError(f"{name} 必须是数字") from exc
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise ValueError(f"{name} 必须在 {minimum:g}-{maximum:g} 范围内")
    return result


def env_bool(name: str, default: bool) -> bool:
    name = _env_name(name)
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
    if any(ch.isspace() for ch in value):
        raise ValueError(f"{name} 不能包含空白字符")
    if "\\" in value:
        raise ValueError(f"{name} 不能包含反斜杠")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{name} URL 格式无效") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{name} 必须是带主机名的 http(s) URL")
    if not _valid_hostname(parsed.hostname):
        raise ValueError(f"{name} 主机名格式无效")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{name} 不能在 URL 中内嵌凭据")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{name} 不能包含查询参数或片段")
    if parsed.netloc.endswith(":") or port == 0:
        raise ValueError(f"{name} 必须使用有效的非零端口")
    return value.rstrip("/")
