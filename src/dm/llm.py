"""LLM 薄客户端（OpenAI 兼容协议，指向 LiteLLM 网关）。

给"无工具的一次性推理"场景用：eval 的 LLM-judge、KG 文档关系抽取。
智能体主循环走 langchain-openai（见 dm/agent/graph.py），两者共用同一网关与模型配置，
换后端（本地 ollama ↔ 云端 deepseek）只改环境变量/网关配置，不改代码。

默认流式（DM_LLM_STREAMING=1）：客户端超时/死亡时连接断开会经网关传导到推理后端，
生成当场中止、并发槽立即释放；非流式请求死后会留下占死槽位的孤儿（DEVLOG 坑27）。
"""
import json
import math
import time

import requests

from dm.config import (LLM_API_KEY, LLM_BASE_URL, LLM_CONNECT_TIMEOUT, LLM_MODEL,
                       LLM_READ_TIMEOUT, LLM_STREAMING)


def _positive_number(value, *, field_name: str):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} 必须是正数: {value!r}")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} 必须是有限正数: {value!r}")
    return value


def chat(messages: list, model: str | None = None, temperature: float = 0.2,
         timeout: int = 180, max_tokens: int | None = None) -> str:
    """一次 chat.completions 调用，返回助手文本内容。

    messages: [{"role": "user"|"system"|"assistant", "content": "..."}]
    timeout: 整次调用的墙钟上限（秒）；流式下另有 connect/token 间隔分层超时。
    失败抛 RuntimeError（带网关/模型报错摘要），由调用方决定兜底。
    """
    timeout = _positive_number(timeout, field_name="timeout")
    payload = {
        "model": model or LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": bool(LLM_STREAMING),
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
    try:
        if not LLM_STREAMING:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        else:
            # 流式：(connect, read) 分层超时——stream 模式下 read 按相邻两次读计，即 token 间隔上限
            r = requests.post(url, json=payload, headers=headers, stream=True,
                              timeout=(LLM_CONNECT_TIMEOUT, LLM_READ_TIMEOUT))
    except requests.RequestException as e:
        raise RuntimeError(f"LLM 网关不可达（{LLM_BASE_URL}）: {e}") from e
    if r.status_code != 200:
        raise RuntimeError(f"LLM 调用失败 HTTP {r.status_code}: {r.text[:300]}")
    if not LLM_STREAMING:
        data = r.json()
        try:
            return data["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"LLM 响应结构异常: {str(data)[:300]}") from e
    # 流式收集：只拼 delta.content（judge/抽取只用终答文本，与非流式取 message.content 等价）
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
        r.close()  # 断开连接：网关据此取消上游生成（僵尸根治点）
    return "".join(parts)
