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


def _run_stream(monkeypatch, line):
    response = _Response([line])
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)
    with pytest.raises(RuntimeError, match="无效 JSON"):
        llm.chat([{"role": "user", "content": "hello"}])
    assert response.closed is True


def test_chat_fails_on_malformed_stream_json(monkeypatch):
    _run_stream(monkeypatch, "data: {bad-json")


def test_chat_rejects_nonstandard_stream_json_constants(monkeypatch):
    _run_stream(monkeypatch, 'data: {"choices":[{"delta":{"content":"ok"}}],"usage":NaN}')


def test_chat_rejects_duplicate_stream_json_keys(monkeypatch):
    _run_stream(
        monkeypatch,
        'data: {"choices":[{"delta":{"content":"safe","content":"shadow"}}]}',
    )
