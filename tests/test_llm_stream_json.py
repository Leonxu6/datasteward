"""Streaming LLM JSON chunk validation."""

import pytest

import dm.llm as llm


class _Response:
    status_code = 200
    text = ""

    def __init__(self, lines):
        self.lines = lines
        self.closed = False

    def iter_lines(self, decode_unicode=True):
        yield from self.lines

    def close(self):
        self.closed = True


def test_chat_fails_on_malformed_stream_json(monkeypatch):
    response = _Response(["data: {bad-json"])
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)

    with pytest.raises(RuntimeError, match="无效 JSON"):
        llm.chat([{"role": "user", "content": "hello"}])

    assert response.closed is True
