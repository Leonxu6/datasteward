"""钉钉通道：把智能体接到钉钉。

模式：
  stream  —— Stream 双向：群聊 @机器人 / 单聊直接提问。
  push    —— HTTPS Webhook 单向推送。
  selftest—— 不连钉钉，验证问题 → 智能体 → 回复链路。
"""
import asyncio
import base64
import hashlib
import hmac
import math
import os
import re
import sys
import time
from collections import OrderedDict, deque

import requests

from dm.agent import run_agent
from dm.channels.validation import (
    append_query_params,
    normalize_message_text,
    normalize_nonnegative_int,
    normalize_positive_float,
    normalize_positive_int,
    normalize_webhook_url,
)

DEFAULT_ROLE = "仓管"


def _normalize_secret(value):
    if value is None or "__FILL_ME__" in str(value):
        return None
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("DINGTALK_WEBHOOK_SECRET 必须是非空且无首尾空白的字符串")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("DINGTALK_WEBHOOK_SECRET 不能包含控制字符")
    return value


def push_webhook(text, webhook=None, secret=None):
    """向钉钉自定义群机器人发送一条经过前置校验的文本消息。"""
    webhook = webhook or os.environ.get("DINGTALK_WEBHOOK")
    if not webhook or "__FILL_ME__" in str(webhook):
        raise SystemExit("缺少 DINGTALK_WEBHOOK（钉钉群『自定义机器人』的 webhook 地址）。")
    webhook = normalize_webhook_url(webhook)
    text = normalize_message_text(text, max_length=20_000)
    secret = _normalize_secret(secret if secret is not None else os.environ.get("DINGTALK_WEBHOOK_SECRET"))

    url = webhook
    if secret:
        ts = str(round(time.time() * 1000))
        sign = base64.b64encode(
            hmac.new(secret.encode("utf-8"), f"{ts}\n{secret}".encode("utf-8"), hashlib.sha256).digest()
        ).decode("ascii")
        url = append_query_params(webhook, timestamp=ts, sign=sign)

    resp = requests.post(url, json={"msgtype": "text", "text": {"content": text}}, timeout=15)
    resp.raise_for_status()
    print("钉钉返回:", resp.status_code, resp.text)
    return resp


def should_trigger(incoming) -> tuple[bool, str]:
    """判定消息是否触发智能体，并返回清洗后的正文。"""
    raw = getattr(getattr(incoming, "text", None), "content", "")
    text = raw.strip() if isinstance(raw, str) else ""
    text = re.sub(r"^@\S+\s+", "", text).strip()
    if not text:
        return False, ""
    if str(getattr(incoming, "conversation_type", "") or "") == "2":
        if bool(getattr(incoming, "is_in_at_list", False)):
            return True, text
        bot_id = str(getattr(incoming, "chatbot_user_id", "") or "")
        at_ids = {
            str(getattr(user, "dingtalk_id", "") or "")
            for user in (getattr(incoming, "at_users", None) or [])
        }
        return bool(bot_id) and bot_id in at_ids, text
    return True, text


class _RoleMap:
    """钉钉 staff_id → 平台角色映射，按 mtime 热加载。"""

    def __init__(self, path=None):
        self.path = path or os.environ.get("DM_ROLE_MAP", "role_map.yaml")
        self._mtime = None
        self._map: dict[str, str] = {}

    def _refresh(self):
        try:
            mtime = os.stat(self.path).st_mtime
        except OSError:
            self._mtime, self._map = None, {}
            return
        if mtime == self._mtime:
            return
        try:
            import yaml

            with open(self.path, encoding="utf-8") as handle:
                document = yaml.safe_load(handle) or {}
            if not isinstance(document, dict):
                raise ValueError("role map root must be a mapping")
            raw = document.get("roles") or {}
            if not isinstance(raw, dict):
                raise ValueError("roles must be a mapping")
            normalized: dict[str, str] = {}
            for sid, value in raw.items():
                role = value.get("role") if isinstance(value, dict) else value
                role = str(role or DEFAULT_ROLE).strip() or DEFAULT_ROLE
                normalized[str(sid).strip()] = role
            self._map = normalized
            print(f"[钉钉] 角色映射已加载：{len(self._map)} 人（{self.path}）")
        except Exception as exc:  # noqa: BLE001
            print(f"[钉钉] 角色映射解析失败（{exc}），全员按默认角色「{DEFAULT_ROLE}」")
            self._map = {}
        self._mtime = mtime

    def role_of(self, staff_id) -> str:
        self._refresh()
        return self._map.get(str(staff_id or "").strip(), DEFAULT_ROLE)


def resolve_identity(incoming, role_map: _RoleMap) -> tuple[str, str]:
    """从钉钉消息解析审计 user 与平台角色。"""
    raw_user = getattr(incoming, "sender_nick", "") or getattr(incoming, "sender_staff_id", "") or "钉钉用户"
    user = str(raw_user).strip() or "钉钉用户"
    user = user[:120]
    role = role_map.role_of(getattr(incoming, "sender_staff_id", ""))
    return user, role


class _Gate:
    """并发闸门：限定活跃任务、等待队列和排队超时。"""

    def __init__(self, limit=None, queue_max=None, queue_timeout=None):
        limit = os.environ.get("DM_DT_CONCURRENCY", "4") if limit is None else limit
        queue_max = os.environ.get("DM_DT_QUEUE_MAX", "12") if queue_max is None else queue_max
        queue_timeout = os.environ.get("DM_DT_QUEUE_TIMEOUT", "300") if queue_timeout is None else queue_timeout
        self.limit = normalize_positive_int(limit, field_name="DM_DT_CONCURRENCY", default=4, maximum=64)
        self.queue_max = normalize_nonnegative_int(queue_max, field_name="DM_DT_QUEUE_MAX", default=12, maximum=1000)
        self.queue_timeout = normalize_positive_float(
            queue_timeout, field_name="DM_DT_QUEUE_TIMEOUT", default=300, maximum=3600
        )
        self.sem = asyncio.Semaphore(self.limit)
        self.active = 0
        self.waiting = 0
        self.durations: deque = deque(maxlen=10)

    @property
    def full(self) -> bool:
        return self.active >= self.limit

    def eta_text(self) -> str:
        """返回入队前的保守等待时间估算。"""
        ahead = self.active + self.waiting
        avg = (sum(self.durations) / len(self.durations)) if self.durations else 60.0
        eta = math.ceil((self.waiting + 1) / self.limit) * avg
        eta = max(30, int(math.ceil(eta / 30.0) * 30))
        return (
            f"已收到。当前提问较多，你前面还有 {ahead} 个问题在处理或排队，"
            f"预计等待约 {eta} 秒，轮到后我会直接在这里回答。"
        )

    def reject_text(self, timed_out: bool) -> str:
        if timed_out:
            minutes = max(1, round(self.queue_timeout / 60))
            return f"排队等了约 {minutes} 分钟还没轮到，这条就不继续占位了——请稍后重发一次，抱歉。"
        return "现在排队的问题太多，这条先不排了——请过几分钟再发一次，抱歉。"


def run_stream():
    """Stream 双向：监听钉钉机器人消息，回答后返回钉钉。"""
    import dingtalk_stream

    app_key = os.environ.get("DINGTALK_APP_KEY")
    app_secret = os.environ.get("DINGTALK_APP_SECRET")
    if not (app_key and app_secret):
        raise SystemExit(
            "缺少 DINGTALK_APP_KEY / DINGTALK_APP_SECRET。"
            "请先在钉钉开放平台自建内部应用 + 机器人（Stream 模式），再设置这两个环境变量。"
        )

    role_map = _RoleMap()
    gate = _Gate()
    purpose = os.environ.get("DM_DT_PURPOSE", "日常问询")

    class Handler(dingtalk_stream.ChatbotHandler):
        _seen: OrderedDict = OrderedDict()

        async def process(self, callback):
            try:
                mid = (callback.headers or {}).get("messageId", "")
            except Exception:  # noqa: BLE001
                mid = ""
            incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            mid = mid or getattr(incoming, "message_id", "") or ""
            if mid and mid in self._seen:
                return dingtalk_stream.AckMessage.STATUS_OK, "OK"
            if mid:
                self._seen[mid] = None
                while len(self._seen) > 512:
                    self._seen.popitem(last=False)

            ctype = "群聊" if str(getattr(incoming, "conversation_type", "") or "") == "2" else "单聊"
            ok, text = should_trigger(incoming)
            if not ok:
                if text:
                    print(f"[钉钉] {ctype}未@，忽略: {text[:50]}")
                return dingtalk_stream.AckMessage.STATUS_OK, "OK"
            user, role = resolve_identity(incoming, role_map)
            staff = getattr(incoming, "sender_staff_id", "") or "?"
            print(f"[钉钉] 收到({ctype}) user={user} staff={staff} role={role}: {text}")

            def push(message):
                self.reply_text(message, incoming)

            async def work():
                loop = asyncio.get_running_loop()
                try:
                    if gate.waiting >= gate.queue_max and gate.full:
                        await loop.run_in_executor(None, push, gate.reject_text(False))
                        return
                    if gate.full:
                        await loop.run_in_executor(None, push, gate.eta_text())
                    gate.waiting += 1
                    try:
                        await asyncio.wait_for(gate.sem.acquire(), timeout=gate.queue_timeout)
                    except asyncio.TimeoutError:
                        await loop.run_in_executor(None, push, gate.reject_text(True))
                        return
                    finally:
                        gate.waiting -= 1
                    gate.active += 1
                    t0 = time.monotonic()
                    try:
                        result = await loop.run_in_executor(
                            None,
                            lambda: run_agent(
                                text,
                                channel="dingtalk",
                                on_step=push,
                                user=user,
                                role=role,
                                purpose=purpose,
                            ),
                        )
                        duration = time.monotonic() - t0
                        print(f"[钉钉] 已回复（会话 {result['session_id']}，{duration:.0f}s，user={user} role={role}）")
                    finally:
                        gate.active -= 1
                        gate.durations.append(time.monotonic() - t0)
                        gate.sem.release()
                except Exception as exc:  # noqa: BLE001
                    try:
                        self.reply_text(f"抱歉，处理出错：{exc}", incoming)
                    except Exception:  # noqa: BLE001
                        pass

            asyncio.create_task(work())
            return dingtalk_stream.AckMessage.STATUS_OK, "OK"

    credential = dingtalk_stream.Credential(app_key, app_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    register = getattr(client, "register_callback_handler", None) or client.register_callback
    register(dingtalk_stream.ChatbotMessage.TOPIC, Handler())
    print(
        f"钉钉 Stream 已启动（双向）。群聊 @机器人 / 单聊直接提问。并发上限 {gate.limit}，"
        f"角色映射 {role_map.path}。Ctrl+C 退出。"
    )
    client.start_forever()


def selftest(question):
    question = normalize_message_text(question, field_name="question", max_length=20_000)
    print(f"[自测] 模拟钉钉收到提问: {question}")
    result = run_agent(question, channel="dingtalk")
    print(f"[自测] 智能体会话: {result['session_id']}")
    print(f"[自测] 将返回钉钉的内容:\n{result['answer']}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if mode == "stream":
        run_stream()
    elif mode == "push":
        push_webhook(" ".join(sys.argv[2:]) or "（来自数据平台的测试推送）")
    elif mode == "selftest":
        selftest(" ".join(sys.argv[2:]) or "物料 M0001 现在总库存多少？分布在哪些仓库？")
    else:
        raise SystemExit(f"未知模式 {mode!r}；可选 stream / push / selftest")


if __name__ == "__main__":
    main()
