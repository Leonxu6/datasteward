"""Streaming LLM empty SSE event handling."""

import json

import dm.llm as llm


class _Response:
    status_code = 200
    text = ""

    def __init__(self):
        self.closed = False

    def iter_lines(self, decode_unicode=True):
        yield "data:"
        yield "data:   "
        yield "data: " + json.dumps({"choices": [{"delta": {"content": "ok"}}]})
        yield "data: [DONE]"

    def close(self):
        self.closed = True


def test_chat_ignores_empty_sse_data_events(monkeypatch):
    response = _Response()
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)

    assert llm.chat([{"role": "user", "content": "hello"}]) == "ok"
    assert response.closed is True
