"""LLM 薄客户端（OpenAI 兼容协议，指向 LiteLLM 网关）。

给"无工具的一次性推理"场景用：eval 的 LLM-judge、KG 文档关系抽取。
智能体主循环走 langchain-openai（见 dm/agent/graph.py），两者共用同一网关与模型配置，
换后端（本地 ollama ↔ 云端 deepseek）只改环境变量/网关配置，不改代码。

默认流式（DM_LLM_STREAMING=1）：客户端超时/死亡时连接断开会经网关传导到推理后端，
生成当场中止、并发槽立即释放；非流式请求死后会留下占死槽位的孤儿（DEVLOG 坑27）。
"""
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


def chat(messages: list, model: str | None = None, temperature: float = 0.2,
         timeout: int = 180, max_tokens: int | None = None) -> str:
    """一次 chat.completions 调用，返回助手文本内容。"""
    messages = _validate_messages(messages)
    model = _required_text(LLM_MODEL if model is None else model, field_name="model")
    timeout = _positive_number(timeout, field_name="timeout")
    max_tokens = _optional_positive_int(max_tokens, field_name="max_tokens")
    temperature = _finite_number(temperature, field_name="temperature")
    payload = {"model": model, "messages": messages, "temperature": temperature, "stream": bool(LLM_STREAMING)}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
    try:
        if not LLM_STREAMING:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        else:
            r = requests.post(url, json=payload, headers=headers, stream=True,
                              timeout=(LLM_CONNECT_TIMEOUT, LLM_READ_TIMEOUT))
    except requests.RequestException as e:
        raise RuntimeError(f"LLM 网关不可达（{LLM_BASE_URL}）: {e}") from e
    if r.status_code != 200:
        raise RuntimeError(f"LLM 调用失败 HTTP {r.status_code}: {r.text[:300]}")
    if not LLM_STREAMING:
        try:
            data = r.json()
        except ValueError as exc:
            raise RuntimeError("LLM 响应不是有效 JSON") from exc
        try:
            return data["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"LLM 响应结构异常: {str(data)[:300]}") from e
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
            except ValueError:
                continue
            if obj.get("error"):
                raise RuntimeError(f"LLM 流式响应报错: {str(obj)[:300]}")
            choices = obj.get("choices") or []
            if choices:
                parts.append((choices[0].get("delta") or {}).get("content") or "")
    except requests.RequestException as e:
        raise RuntimeError(f"LLM 流式读取中断: {e}") from e
    finally:
        r.close()
    return "".join(parts)
