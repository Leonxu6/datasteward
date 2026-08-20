"""LLM 薄客户端（OpenAI 兼容协议，指向 LiteLLM 网关）。"""
import json
import math
import operator
import time

import requests

from dm.config import (LLM_API_KEY, LLM_BASE_URL, LLM_CONNECT_TIMEOUT, LLM_MODEL,
                       LLM_READ_TIMEOUT, LLM_STREAMING)


def _finite_number(value, *, field_name: str):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field_name} 必须是有限数字: {value!r}")
    return value


def _positive_number(value, *, field_name: str):
    value = _finite_number(value, field_name=field_name)
    if value <= 0:
        raise ValueError(f"{field_name} 必须大于 0: {value!r}")
    return value


def _optional_positive_int(value, *, field_name: str):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是正整数，不能是布尔值: {value!r}")
    try:
        parsed = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"{field_name} 必须是正整数: {value!r}") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} 必须大于 0: {parsed}")
    return parsed


def _required_text(value, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} 必须是非空字符串: {value!r}")
    if value != value.strip():
        raise ValueError(f"{field_name} 不能包含首尾空白: {value!r}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field_name} 不能包含控制字符: {value!r}")
    return value


def _validate_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages 必须是非空列表")
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"messages[{index}] 必须是对象")
        role = message.get("role")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"messages[{index}].role 必须是非空字符串")
        if "content" not in message:
            raise ValueError(f"messages[{index}] 缺少 content")
    return messages


def _nonstream_content(data) -> str:
    try:
        content = data["choices"][0]["message"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError(f"LLM 响应结构异常: {str(data)[:300]}") from exc
    if content is None:
        return ""
    if not isinstance(content, str):
        raise RuntimeError(f"LLM 响应 content 不是文本: {type(content).__name__}")
    return content


def _stream_content(obj):
    if not isinstance(obj, dict):
        raise RuntimeError(f"LLM 流式响应结构异常: {str(obj)[:300]}")
    if obj.get("error"):
        raise RuntimeError(f"LLM 流式响应报错: {str(obj)[:300]}")
    choices = obj.get("choices") or []
    if not isinstance(choices, list):
        raise RuntimeError(f"LLM 流式 choices 结构异常: {str(obj)[:300]}")
    if not choices:
        return None
    choice = choices[0]
    if not isinstance(choice, dict):
        raise RuntimeError(f"LLM 流式 choice 结构异常: {str(choice)[:300]}")
    delta = choice.get("delta") or {}
    if not isinstance(delta, dict):
        raise RuntimeError(f"LLM 流式 delta 结构异常: {str(delta)[:300]}")
    content = delta.get("content")
    if content is None:
        return None
    if not isinstance(content, str):
        raise RuntimeError(f"LLM 流式 content 不是文本: {type(content).__name__}")
    return content


def chat(messages: list, model: str | None = None, temperature: float = 0.2,
         timeout: int = 180, max_tokens: int | None = None) -> str:
    messages = _validate_messages(messages)
    model = _required_text(LLM_MODEL if model is None else model, field_name="model")
    base_url = _required_text(LLM_BASE_URL, field_name="LLM_BASE_URL")
    timeout = _positive_number(timeout, field_name="timeout")
    max_tokens = _optional_positive_int(max_tokens, field_name="max_tokens")
    temperature = _finite_number(temperature, field_name="temperature")
    payload = {"model": model, "messages": messages, "temperature": temperature, "stream": bool(LLM_STREAMING)}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
    try:
        if not LLM_STREAMING:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        else:
            connect_timeout = min(_positive_number(LLM_CONNECT_TIMEOUT, field_name="LLM_CONNECT_TIMEOUT"), timeout)
            read_timeout = min(_positive_number(LLM_READ_TIMEOUT, field_name="LLM_READ_TIMEOUT"), timeout)
            r = requests.post(url, json=payload, headers=headers, stream=True,
                              timeout=(connect_timeout, read_timeout))
    except requests.RequestException as e:
        raise RuntimeError(f"LLM 网关不可达（{base_url}）: {e}") from e
    if r.status_code != 200:
        try:
            detail = r.text[:300]
        finally:
            r.close()
        raise RuntimeError(f"LLM 调用失败 HTTP {r.status_code}: {detail}")
    if not LLM_STREAMING:
        try:
            try:
                data = r.json()
            except ValueError as exc:
                raise RuntimeError("LLM 响应不是有效 JSON") from exc
            return _nonstream_content(data)
        finally:
            r.close()
    parts: list[str] = []
    deadline = time.monotonic() + timeout
    try:
        for line in r.iter_lines(decode_unicode=True):
            if time.monotonic() > deadline:
                raise RuntimeError(f"LLM 调用超墙钟 {timeout}s，已断开连接止损")
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError as exc:
                raise RuntimeError(f"LLM 流式响应包含无效 JSON: {data[:200]}") from exc
            content = _stream_content(obj)
            if content is not None:
                parts.append(content)
    except requests.RequestException as e:
        raise RuntimeError(f"LLM 流式读取中断: {e}") from e
    finally:
        r.close()
    return "".join(parts)
