"""钉钉通道：把智能体接到钉钉（可插拔通道；与管理平台、eval 共用同一个 run_agent）。

模式：
  stream  —— Stream 双向（主入口）：钉钉里 @机器人 提问 → 智能体经 MCP 查仓库 → 回答返回钉钉。
            需 DINGTALK_APP_KEY / DINGTALK_APP_SECRET（钉钉开放平台自建内部应用+机器人后获得）。
            运行: dm-dingtalk stream
  push    —— Webhook 单向：把文本推到钉钉群（自定义群机器人，零审批）。
            需 DINGTALK_WEBHOOK（可选 DINGTALK_WEBHOOK_SECRET）。
            运行: dm-dingtalk push "文本"
  selftest—— 不连钉钉，验证"收到提问→跑智能体→生成回复"链路是否正常。
            运行: dm-dingtalk selftest "物料 M0001 现在总库存多少？"

组织级接入（PR⑧）：
  触发    —— 群聊仅响应 @机器人（防闲聊误触发烧 GPU）；单聊任意文本直通。
  身份    —— sender_nick 透传为审计 user；staff_id 经 role_map.yaml 映射平台角色
            （mtime 热加载，未列入者默认最小权限「仓管」）——同一问题不同人答案不同。
  并发    —— 闸门 DM_DT_CONCURRENCY(4) 与 ollama 槽位对齐；满载即时反馈排队位次与预计等待，
            排队超 DM_DT_QUEUE_TIMEOUT(300s) 礼貌拒绝出队，队深超 DM_DT_QUEUE_MAX(12) 直接拒。
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
import urllib.parse
from collections import OrderedDict, deque

import requests

from dm.agent import run_agent

DEFAULT_ROLE = "仓管"   # 未映射者的最小权限角色（与 dm/tools/principal.py 默认一致）


def push_webhook(text, webhook=None, secret=None):
    """自定义群机器人单向推送。"""
    webhook = webhook or os.environ.get("DINGTALK_WEBHOOK")
    secret = secret or os.environ.get("DINGTALK_WEBHOOK_SECRET")
    if not webhook or "__FILL_ME__" in webhook:  # .env 模板占位符=未配置
        raise SystemExit("缺少 DINGTALK_WEBHOOK（钉钉群『自定义机器人』的 webhook 地址）。")
    if secret and "__FILL_ME__" in secret:
        secret = None
    url = webhook
    if secret:
        ts = str(round(time.time() * 1000))
        sign = base64.b64encode(
            hmac.new(secret.encode("utf-8"), f"{ts}\n{secret}".encode("utf-8"), hashlib.sha256).digest())
        url = f"{webhook}&timestamp={ts}&sign={urllib.parse.quote_plus(sign)}"
    resp = requests.post(url, json={"msgtype": "text", "text": {"content": text}}, timeout=15)
    print("钉钉返回:", resp.status_code, resp.text)
    return resp


def should_trigger(incoming) -> tuple[bool, str]:
    """判定一条钉钉消息是否触发智能体，并返回清洗后的问题文本。

    群聊（conversation_type=='2'）仅响应 @机器人（is_in_at_list 为主，
    缺失时回退 at_users 匹配 chatbot_user_id）；单聊（'1'）任意非空文本直通。
    """
    text = (incoming.text.content if getattr(incoming, "text", None) else "").strip()
    text = re.sub(r"^@\S+\s+", "", text).strip()  # 防御：个别客户端把 @机器人 写进正文
    if not text:
        return False, ""
    if str(getattr(incoming, "conversation_type", "") or "") == "2":
        if bool(getattr(incoming, "is_in_at_list", False)):
            return True, text
        bot_id = str(getattr(incoming, "chatbot_user_id", "") or "")
        at_ids = {str(getattr(u, "dingtalk_id", "") or "") for u in (getattr(incoming, "at_users", None) or [])}
        return bool(bot_id) and bot_id in at_ids, text
    return True, text


class _RoleMap:
    """钉钉 staff_id → 平台角色映射（mtime 热加载：改完文件即生效，无需重启）。

    文件缺失/解析失败 → 空表（全员默认「仓管」）+ 日志，绝不因配置问题崩通道。
    值支持 `staff_id: 角色` 或 `staff_id: {role: 角色, ...}`（预留行级属性扩展）。
    """

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
            with open(self.path, encoding="utf-8") as f:
                raw = (yaml.safe_load(f) or {}).get("roles") or {}
            self._map = {str(sid): str(v.get("role") or DEFAULT_ROLE) if isinstance(v, dict) else str(v)
                         for sid, v in raw.items()}
            print(f"[钉钉] 角色映射已加载：{len(self._map)} 人（{self.path}）")
        except Exception as e:  # noqa: BLE001
            print(f"[钉钉] 角色映射解析失败（{e}），全员按默认角色「{DEFAULT_ROLE}」")
            self._map = {}
        self._mtime = mtime

    def role_of(self, staff_id) -> str:
        self._refresh()
        return self._map.get(str(staff_id or ""), DEFAULT_ROLE)


def resolve_identity(incoming, role_map: _RoleMap) -> tuple[str, str]:
    """提问者身份：昵称透传为审计 user（谁问的一目了然），staff_id 定角色（PBAC 按人生效）。"""
    user = str(getattr(incoming, "sender_nick", "") or getattr(incoming, "sender_staff_id", "") or "钉钉用户")
    role = role_map.role_of(getattr(incoming, "sender_staff_id", ""))
    return user, role


class _Gate:
    """并发闸门：同时处理上限 limit（与 ollama 槽位留余量对齐），满载排队并即时反馈，
    排队超时礼貌拒绝。近 10 次耗时估 ETA。所有状态只在单事件循环内读写，无需加锁。"""

    def __init__(self, limit=None, queue_max=None, queue_timeout=None):
        self.limit = int(limit or os.environ.get("DM_DT_CONCURRENCY", "4"))
        self.queue_max = int(queue_max or os.environ.get("DM_DT_QUEUE_MAX", "12"))
        self.queue_timeout = float(queue_timeout or os.environ.get("DM_DT_QUEUE_TIMEOUT", "300"))
        self.sem = asyncio.Semaphore(self.limit)
        self.active = 0
        self.waiting = 0
        self.durations: deque = deque(maxlen=10)

    @property
    def full(self) -> bool:
        return self.active >= self.limit

    def eta_text(self) -> str:
        """排队反馈文案（入队前调用）：位次 = 正在处理+已在排队的问题数。"""
        ahead = self.active + self.waiting
        avg = (sum(self.durations) / len(self.durations)) if self.durations else 60.0
        eta = math.ceil((self.waiting + 1) / self.limit) * avg
        eta = max(30, int(math.ceil(eta / 30.0) * 30))  # 30s 粒度，至少 30s
        return (f"已收到。当前提问较多，你前面还有 {ahead} 个问题在处理或排队，"
                f"预计等待约 {eta} 秒，轮到后我会直接在这里回答。")

    def reject_text(self, timed_out: bool) -> str:
        if timed_out:
            return "排队等了 5 分钟还没轮到（当前提问太集中），这条就不继续占位了——请稍后重发一次，抱歉。"
        return "现在排队的问题太多，这条先不排了——请过几分钟再发一次，抱歉。"


def run_stream():
    """Stream 双向：监听钉钉机器人消息，回答后返回钉钉。"""
    import dingtalk_stream

    app_key = os.environ.get("DINGTALK_APP_KEY")
    app_secret = os.environ.get("DINGTALK_APP_SECRET")
    if not (app_key and app_secret):
        raise SystemExit("缺少 DINGTALK_APP_KEY / DINGTALK_APP_SECRET。"
                         "请先在钉钉开放平台自建内部应用 + 机器人（Stream 模式），再设置这两个环境变量。")

    role_map = _RoleMap()
    gate = _Gate()
    purpose = os.environ.get("DM_DT_PURPOSE", "日常问询")

    class Handler(dingtalk_stream.ChatbotHandler):
        _seen: OrderedDict = OrderedDict()  # messageId 去重，FIFO 上限 512（防组织级放量内存慢涨）

        async def process(self, callback):
            mid = ""
            try:
                mid = (callback.headers or {}).get("messageId", "")
            except Exception:  # noqa: BLE001
                mid = ""
            incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            mid = mid or getattr(incoming, "message_id", "") or ""
            # 智能体一次作答要十几秒~两分钟，远超钉钉的 ACK 超时。必须【立刻 ACK】并后台处理，
            # 否则钉钉判定投递失败会重复下发同一条消息 → 机器人重复回复。再以 messageId 去重兜底。
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

            def push(m):
                # 把智能体每一步原生过程实时发到钉钉（边做边发）。在 executor 线程里调用，纯 HTTP，安全。
                self.reply_text(m, incoming)

            async def work():
                loop = asyncio.get_running_loop()
                try:
                    # ---- 并发闸门：满载即时反馈 → 排队 → 超时礼貌拒绝 ----
                    if gate.waiting >= gate.queue_max:
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
                        # on_step 逐步流式；最终结论已作为最后一段流式发出，不再单独重复发
                        result = await loop.run_in_executor(
                            None, lambda: run_agent(text, channel="dingtalk", on_step=push,
                                                    user=user, role=role, purpose=purpose))
                        dur = time.monotonic() - t0
                        print(f"[钉钉] 已回复（会话 {result['session_id']}，{dur:.0f}s，user={user} role={role}）")
                    finally:
                        gate.active -= 1
                        gate.durations.append(time.monotonic() - t0)
                        gate.sem.release()
                except Exception as e:  # noqa: BLE001
                    try:
                        self.reply_text(f"抱歉，处理出错：{e}", incoming)
                    except Exception:  # noqa: BLE001
                        pass

            asyncio.create_task(work())
            return dingtalk_stream.AckMessage.STATUS_OK, "OK"

    cred = dingtalk_stream.Credential(app_key, app_secret)
    client = dingtalk_stream.DingTalkStreamClient(cred)
    # dingtalk-stream >=0.13 改名：register_callback -> register_callback_handler
    register = getattr(client, "register_callback_handler", None) or client.register_callback
    register(dingtalk_stream.ChatbotMessage.TOPIC, Handler())
    print(f"钉钉 Stream 已启动（双向）。群聊 @机器人 / 单聊直接提问。并发上限 {gate.limit}，"
          f"角色映射 {role_map.path}。Ctrl+C 退出。")
    client.start_forever()


def selftest(question):
    print(f"[自测] 模拟钉钉收到提问: {question}")
    r = run_agent(question, channel="dingtalk")
    print(f"[自测] 智能体会话: {r['session_id']}")
    print(f"[自测] 将返回钉钉的内容:\n{r['answer']}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if mode == "stream":
        run_stream()
    elif mode == "push":
        push_webhook(" ".join(sys.argv[2:]) or "（来自数据平台的测试推送）")
    else:
        selftest(" ".join(sys.argv[2:]) or "物料 M0001 现在总库存多少？分布在哪些仓库？")


if __name__ == "__main__":
    main()
