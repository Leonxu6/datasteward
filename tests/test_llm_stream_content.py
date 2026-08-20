"""Streaming LLM content type validation."""

import json

import pytest

import dm.llm as llm


class _Response:
    status_code = 200
    text = ""

    def __init__(self, content):
        self.content = content
        self.closed = False

    def iter_lines(self, decode_unicode=True):
        yield "data: " + json.dumps({"choices": [{"delta": {"content": self.content}}]})
        yield "data: [DONE]"

    def close(self):
        self.closed = True


@pytest.mark.parametrize("content", [123, True, [], {}, ["text"]])
def test_chat_rejects_non_text_stream_content(monkeypatch, content):
    response = _Response(content)
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)

    with pytest.raises(RuntimeError, match="content 不是文本"):
        llm.chat([{"role": "user", "content": "hello"}])

    assert response.closed is True


def test_chat_ignores_null_stream_content(monkeypatch):
    response = _Response(None)
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)

    assert llm.chat([{"role": "user", "content": "hello"}]) == ""
    assert response.closed is True
