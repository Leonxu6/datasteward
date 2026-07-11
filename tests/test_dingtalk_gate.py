"""钉钉组织级接入的确定性单测：触发过滤 / 角色映射热加载 / 并发闸门 / LLM 流式解析。

不连钉钉、不连网关：消息用鸭子类型桩（should_trigger/resolve_identity 全走 getattr），
LLM 流式用打桩 requests.post 喂伪 SSE。真实字段名与端到端行为由 GB10 真实入口验收覆盖。
"""
import asyncio
import os
import time
from types import SimpleNamespace

import pytest

from dm.channels.dingtalk import DEFAULT_ROLE, _Gate, _RoleMap, resolve_identity, should_trigger


def _msg(text="库存多少", ctype="2", at=False, bot_id="bot1", at_ids=(), nick="张三", staff="s001"):
    return SimpleNamespace(
        text=SimpleNamespace(content=text),
        conversation_type=ctype,
        is_in_at_list=at,
        chatbot_user_id=bot_id,
        at_users=[SimpleNamespace(dingtalk_id=i) for i in at_ids],
        sender_nick=nick,
        sender_staff_id=staff,
    )


# ---------- 触发过滤 ----------

def test_group_without_at_ignored():
    ok, text = should_trigger(_msg(ctype="2", at=False))
    assert not ok and text == "库存多少"


def test_group_with_at_triggers():
    ok, text = should_trigger(_msg(ctype="2", at=True))
    assert ok and text == "库存多少"


def test_group_at_fallback_via_at_users():
    ok, _ = should_trigger(_msg(ctype="2", at=False, bot_id="bot1", at_ids=("x", "bot1")))
    assert ok


def test_private_chat_passes_through():
    ok, text = should_trigger(_msg(ctype="1", at=False))
    assert ok and text == "库存多少"


def test_empty_and_at_prefix_stripped():
    ok, _ = should_trigger(_msg(text="   ", ctype="1"))
    assert not ok
    ok, text = should_trigger(_msg(text="@数据机器人 M0001 库存", ctype="1"))
    assert ok and text == "M0001 库存"


# ---------- 角色映射（热加载） ----------

def test_role_map_missing_file_defaults(tmp_path):
    rm = _RoleMap(path=str(tmp_path / "nope.yaml"))
    assert rm.role_of("anyone") == DEFAULT_ROLE


def test_role_map_hit_flat_and_extended(tmp_path):
    p = tmp_path / "role_map.yaml"
    p.write_text('roles:\n  "s001": 采购\n  "s002": { role: 管理层, warehouse_id: W01 }\n', encoding="utf-8")
    rm = _RoleMap(path=str(p))
    assert rm.role_of("s001") == "采购"
    assert rm.role_of("s002") == "管理层"
    assert rm.role_of("s999") == DEFAULT_ROLE


def test_role_map_hot_reload_on_mtime(tmp_path):
    p = tmp_path / "role_map.yaml"
    p.write_text('roles:\n  "s001": 采购\n', encoding="utf-8")
    rm = _RoleMap(path=str(p))
    assert rm.role_of("s001") == "采购"
    p.write_text('roles:\n  "s001": 管理层\n', encoding="utf-8")
    os.utime(p, (time.time() + 5, time.time() + 5))  # 强制 mtime 前进，规避文件系统粒度
    assert rm.role_of("s001") == "管理层"


def test_role_map_broken_yaml_degrades(tmp_path):
    p = tmp_path / "role_map.yaml"
    p.write_text("roles: [::broken", encoding="utf-8")
    rm = _RoleMap(path=str(p))
    assert rm.role_of("s001") == DEFAULT_ROLE


def test_resolve_identity_nick_then_staff_then_anon(tmp_path):
    rm = _RoleMap(path=str(tmp_path / "nope.yaml"))
    assert resolve_identity(_msg(nick="张三", staff="s1"), rm) == ("张三", DEFAULT_ROLE)
    assert resolve_identity(_msg(nick="", staff="s1"), rm)[0] == "s1"
    assert resolve_identity(_msg(nick="", staff=""), rm)[0] == "钉钉用户"


# ---------- 并发闸门 ----------

def test_gate_queue_feedback_and_timeout():
    async def main():
        gate = _Gate(limit=1, queue_max=2, queue_timeout=0.15)
        events = []

        async def job(tag, hold):
            if gate.waiting >= gate.queue_max:
                events.append((tag, "rejected_full"))
                return
            if gate.full:
                events.append((tag, "queued", gate.eta_text()))
            gate.waiting += 1
            try:
                await asyncio.wait_for(gate.sem.acquire(), timeout=gate.queue_timeout)
            except asyncio.TimeoutError:
                events.append((tag, "rejected_timeout"))
                return
            finally:
                gate.waiting -= 1
            gate.active += 1
            t0 = time.monotonic()
            try:
                events.append((tag, "run"))
                await asyncio.sleep(hold)
            finally:
                gate.active -= 1
                gate.durations.append(time.monotonic() - t0)
                gate.sem.release()

        t1 = asyncio.create_task(job("A", 0.3))   # 占住唯一槽 0.3s
        while gate.active == 0:                   # Windows 循环 sleep(0.01)≈0，须显式等 A 真拿到槽
            await asyncio.sleep(0.01)
        t2 = asyncio.create_task(job("B", 0.05))  # 满载 → 收排队反馈，0.15s 内等不到 → 超时拒绝
        await asyncio.gather(t1, t2)
        return events, gate

    events, gate = asyncio.run(main())
    tags = [(e[0], e[1]) for e in events]
    assert ("A", "run") in tags
    assert ("B", "queued") in tags
    assert ("B", "rejected_timeout") in tags
    eta_msg = next(e[2] for e in events if e[1] == "queued")
    assert "前面还有 1 个" in eta_msg and "秒" in eta_msg
    assert gate.active == 0 and gate.waiting == 0        # 终态归零
    assert len(gate.durations) == 1                       # 只有 A 真正跑完喂了耗时


def test_gate_eta_defaults_and_rounding():
    gate = _Gate(limit=4, queue_max=12, queue_timeout=300)
    assert "约 60 秒" in gate.eta_text()                  # 无样本按 60s
    gate.durations.extend([100.0])
    gate.active = 4
    assert "约 120 秒" in gate.eta_text()                 # ceil(1/4)*100 → 30s 粒度上取整


# ---------- dm.llm.chat 流式解析 ----------

class _FakeResp:
    def __init__(self, lines, status=200):
        self.status_code = status
        self._lines = lines
        self.closed = False
        self.text = ""

    def iter_lines(self, decode_unicode=True):
        yield from self._lines

    def close(self):
        self.closed = True


def _sse(*chunks, done=True):
    lines = ['data: {"choices":[{"delta":{"content":"%s"}}]}' % c for c in chunks]
    if done:
        lines.append("data: [DONE]")
    return lines


def test_llm_chat_stream_collects_content(monkeypatch):
    import dm.llm as llm
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    resp = _FakeResp(_sse("你好", "，", "世界"))
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: resp)
    assert llm.chat([{"role": "user", "content": "hi"}]) == "你好，世界"
    assert resp.closed


def test_llm_chat_stream_error_block(monkeypatch):
    import dm.llm as llm
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    resp = _FakeResp(['data: {"error":{"message":"boom"}}'])
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: resp)
    with pytest.raises(RuntimeError, match="流式响应报错"):
        llm.chat([{"role": "user", "content": "hi"}])
    assert resp.closed


def test_llm_chat_stream_wall_timeout(monkeypatch):
    import dm.llm as llm
    monkeypatch.setattr(llm, "LLM_STREAMING", True)

    class _SlowResp(_FakeResp):
        def iter_lines(self, decode_unicode=True):
            while True:  # 无限流，靠墙钟斩断
                yield 'data: {"choices":[{"delta":{"content":"x"}}]}'

    resp = _SlowResp([])
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: resp)
    t = {"n": 0}
    real = time.monotonic
    monkeypatch.setattr(llm.time, "monotonic", lambda: real() + (t.__setitem__("n", t["n"] + 1) or t["n"] * 3.0))
    with pytest.raises(RuntimeError, match="超墙钟"):
        llm.chat([{"role": "user", "content": "hi"}], timeout=5)
    assert resp.closed  # 超时后连接已关闭（取消传导）


def test_llm_chat_nonstream_fallback(monkeypatch):
    import dm.llm as llm
    monkeypatch.setattr(llm, "LLM_STREAMING", False)

    class _JsonResp:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "老路径"}}]}

    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _JsonResp())
    assert llm.chat([{"role": "user", "content": "hi"}]) == "老路径"
