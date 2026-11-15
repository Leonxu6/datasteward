"""Non-stream LLM response JSON handling."""

import pytest

import dm.llm as llm


class _StreamingResponse:
    status_code = 200

    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    def iter_content(self, *, chunk_size):
        assert chunk_size == llm._RESPONSE_CHUNK_BYTES
        yield from self.chunks

    def close(self):
        self.closed = True


def test_chat_surfaces_invalid_nonstream_json(monkeypatch):
    class _Response:
        status_code = 200
        text = "not-json"

        def json(self):
            raise ValueError("decode failed")

    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: _Response())

    with pytest.raises(RuntimeError, match="不是有效 JSON"):
        llm.chat([{"role": "user", "content": "hello"}])


def test_chat_streams_and_bounds_nonstream_response_body(monkeypatch):
    response = _StreamingResponse([b"x" * 33, b"y" * 32])
    captured = {}
    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(llm, "_MAX_NONSTREAM_RESPONSE_BYTES", 64)
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: captured.update(kwargs) or response,
    )

    with pytest.raises(RuntimeError, match="正文超过大小上限"):
        llm.chat([{"role": "user", "content": "hello"}])

    assert captured["stream"] is True
    assert response.closed is True


def test_chat_strictly_decodes_streamed_nonstream_json(monkeypatch):
    response = _StreamingResponse([
        b'{"choices":[{"message":{"content":"ok"}}],',
        b'"choices":[]}',
    ])
    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)

    with pytest.raises(RuntimeError, match="不是有效 JSON"):
        llm.chat([{"role": "user", "content": "hello"}])

    assert response.closed is True
