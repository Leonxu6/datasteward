"""Streaming LLM response envelope validation."""

import json

import pytest

import dm.llm as llm


class _Response:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self.payload = payload
        self.closed = False

    def iter_lines(self, decode_unicode=True):
        yield "data: " + json.dumps(self.payload)

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    "payload",
    [[], {"choices": "bad"}, {"choices": [123]}, {"choices": [{"delta": "bad"}]}],
)
def test_chat_rejects_malformed_stream_envelopes(monkeypatch, payload):
    response = _Response(payload)
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)

    with pytest.raises(RuntimeError, match="流式"):
        llm.chat([{"role": "user", "content": "hello"}])

    assert response.closed is True
