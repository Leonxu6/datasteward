"""Streaming LLM byte-chunk compatibility."""

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


def test_chat_decodes_utf8_byte_stream_chunks(monkeypatch):
    response = _Response([
        'data: {"choices":[{"delta":{"content":"你好"}}]}'.encode("utf-8"),
        b"data: [DONE]",
    ])
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)

    assert llm.chat([{"role": "user", "content": "hello"}]) == "你好"
    assert response.closed is True
