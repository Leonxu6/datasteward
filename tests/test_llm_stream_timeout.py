"""Streaming LLM socket timeout behavior."""

import dm.llm as llm


class _Response:
    status_code = 200
    text = ""

    def iter_lines(self, decode_unicode=True):
        yield "data: [DONE]"

    def close(self):
        pass


def test_stream_socket_timeouts_are_capped_by_wall_timeout(monkeypatch):
    captured = {}
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm, "LLM_CONNECT_TIMEOUT", 30)
    monkeypatch.setattr(llm, "LLM_READ_TIMEOUT", 60)
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: captured.update(kwargs) or _Response(),
    )

    assert llm.chat([{"role": "user", "content": "hello"}], timeout=5) == ""
    assert captured["timeout"] == (5, 5)


def test_stream_socket_timeouts_keep_smaller_configured_limits(monkeypatch):
    captured = {}
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm, "LLM_CONNECT_TIMEOUT", 2)
    monkeypatch.setattr(llm, "LLM_READ_TIMEOUT", 3)
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: captured.update(kwargs) or _Response(),
    )

    assert llm.chat([{"role": "user", "content": "hello"}], timeout=10) == ""
    assert captured["timeout"] == (2, 3)
