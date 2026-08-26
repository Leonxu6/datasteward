"""LLM 薄客户端（OpenAI 兼容协议，指向 LiteLLM 网关）。"""
import json
import math
import operator
import time
from urllib.parse import urlsplit

import requests

from dm.config import (LLM_API_KEY, LLM_BASE_URL, LLM_CONNECT_TIMEOUT, LLM_MODEL,
                       LLM_READ_TIMEOUT, LLM_STREAMING)

_MAX_MESSAGES = 200
_MAX_SERIALIZED_MESSAGES = 1_000_000
_MAX_RESPONSE_CHARS = 1_000_000
_ALLOWED_ROLES = {"system", "user", "assistant", "tool", "function", "developer"}


def _finite_number(value, *, field_name: str):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} 必须是有限数字")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise ValueError(f"{field_name} 必须是有限数字") from exc
    if not finite:
        raise ValueError(f"{field_name} 必须是有限数字")
    return value


def _positive_number(value, *, field_name: str):
    value = _finite_number(value, field_name=field_name)
    if value <= 0:
        raise ValueError(f"{field_name} 必须大于 0")
    return value


def _optional_positive_int(value, *, field_name: str):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是正整数，不能是布尔值")
    try:
        parsed = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"{field_name} 必须是正整数") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} 必须大于 0")
    return parsed


def _required_text(value, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} 必须是非空字符串: {value!r}")
    if value != value.strip():
        raise ValueError(f"{field_name} 不能包含首尾空白: {value!r}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field_name} 不能包含控制字符: {value!r}")
    return value


def _header_value(value, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串: {value!r}")
    if value != value.strip():
        raise ValueError(f"{field_name} 不能包含首尾空白")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field_name} 不能包含控制字符")
    return value


def _gateway_base_url(value) -> str:
    value = _required_text(value, field_name="LLM_BASE_URL")
    if any(ch.isspace() for ch in value) or "\\" in value:
        raise ValueError("LLM_BASE_URL 不能包含空白或反斜杠")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"LLM_BASE_URL 必须是有效的 HTTP(S) URL: {value!r}") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not hostname:
        raise ValueError(f"LLM_BASE_URL 必须是有效的 HTTP(S) URL: {value!r}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("LLM_BASE_URL 不能内嵌凭据")
    if parsed.query or parsed.fragment:
        raise ValueError("LLM_BASE_URL 不能包含查询参数或片段")
    if parsed.netloc.endswith(":") or port == 0:
        raise ValueError("LLM_BASE_URL 必须使用有效的非零端口")
    return value.rstrip("/")


def _validate_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages 必须是非空列表")
    if len(messages) > _MAX_MESSAGES:
        raise ValueError(f"messages 不能超过 {_MAX_MESSAGES} 条")
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"messages[{index}] 必须是对象")
        role = _required_text(message.get("role"), field_name=f"messages[{index}].role")
        if role not in _ALLOWED_ROLES:
            raise ValueError(f"messages[{index}].role 不受支持")
        if "content" not in message:
            raise ValueError(f"messages[{index}] 缺少 content")
    try:
        serialized = json.dumps(messages, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("messages 必须可 JSON 序列化") from exc
    if len(serialized) > _MAX_SERIALIZED_MESSAGES:
        raise ValueError("messages 序列化后过大")
    return messages


def _nonstream_content(data) -> str:
    try:
        content = data["choices"][0]["message"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError("LLM 响应结构异常") from exc
    if content is None:
        return ""
    if not isinstance(content, str):
        raise RuntimeError(f"LLM 响应 content 不是文本: {type(content).__name__}")
    if len(content) > _MAX_RESPONSE_CHARS:
        raise RuntimeError("LLM 响应内容超过大小上限")
    return content


def _stream_content(obj):
    if not isinstance(obj, dict):
        raise RuntimeError("LLM 流式响应结构异常")
    if obj.get("error"):
        raise RuntimeError("LLM 流式响应报错")
    choices = obj.get("choices") or []
    if not isinstance(choices, list):
        raise RuntimeError("LLM 流式 choices 结构异常")
    if not choices:
        return None
    choice = choices[0]
    if not isinstance(choice, dict):
        raise RuntimeError("LLM 流式 choice 结构异常")
    delta = choice.get("delta") or {}
    if not isinstance(delta, dict):
        raise RuntimeError("LLM 流式 delta 结构异常")
    content = delta.get("content")
    if content is None:
        return None
    if not isinstance(content, str):
        raise RuntimeError(f"LLM 流式 content 不是文本: {type(content).__name__}")
    return content


def _close_response(response) -> None:
    """Close requests-compatible responses when the adapter exposes cleanup."""
    close = getattr(response, "close", None)
    if callable(close):
        close()


def chat(messages: list, model: str | None = None, temperature: float = 0.2,
         timeout: int = 180, max_tokens: int | None = None) -> str:
    messages = _validate_messages(messages)
    model = _required_text(LLM_MODEL if model is None else model, field_name="model")
    base_url = _gateway_base_url(LLM_BASE_URL)
    api_key = _header_value(LLM_API_KEY, field_name="LLM_API_KEY")
    timeout = _positive_number(timeout, field_name="timeout")
    max_tokens = _optional_positive_int(max_tokens, field_name="max_tokens")
    temperature = _finite_number(temperature, field_name="temperature")
    payload = {"model": model, "messages": messages, "temperature": temperature, "stream": bool(LLM_STREAMING)}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        if not LLM_STREAMING:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        else:
            connect_timeout = min(_positive_number(LLM_CONNECT_TIMEOUT, field_name="LLM_CONNECT_TIMEOUT"), timeout)
            read_timeout = min(_positive_number(LLM_READ_TIMEOUT, field_name="LLM_READ_TIMEOUT"), timeout)
            r = requests.post(url, json=payload, headers=headers, stream=True,
                              timeout=(connect_timeout, read_timeout))
    except requests.RequestException as e:
        raise RuntimeError(f"LLM 网关不可达（{base_url}）") from e
    if r.status_code != 200:
        _close_response(r)
        raise RuntimeError(f"LLM 调用失败 HTTP {r.status_code}")
    if not LLM_STREAMING:
        try:
            try:
                data = r.json()
            except ValueError as exc:
                raise RuntimeError("LLM 响应不是有效 JSON") from exc
            return _nonstream_content(data)
        finally:
            _close_response(r)
    parts: list[str] = []
    total_chars = 0
    deadline = time.monotonic() + timeout
    try:
        for line in r.iter_lines(decode_unicode=True):
            if time.monotonic() > deadline:
                raise RuntimeError(f"LLM 调用超墙钟 {timeout}s，已断开连接止损")
            if isinstance(line, bytes):
                try:
                    line = line.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise RuntimeError("LLM 流式响应不是有效 UTF-8") from exc
            if not line or not isinstance(line, str) or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if not data:
                continue
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError as exc:
                raise RuntimeError("LLM 流式响应包含无效 JSON") from exc
            content = _stream_content(obj)
            if content is not None:
                total_chars += len(content)
                if total_chars > _MAX_RESPONSE_CHARS:
                    raise RuntimeError("LLM 流式响应内容超过大小上限")
                parts.append(content)
    except requests.RequestException as e:
        raise RuntimeError("LLM 流式读取中断") from e
    finally:
        _close_response(r)
    return "".join(parts)
