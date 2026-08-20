"""LLM HTTP response cleanup behavior."""

import pytest

import dm.llm as llm


class _Response:
    def __init__(self, *, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text
        self.closed = False

    def json(self):
        return self.payload

    def close(self):
        self.closed = True


def test_nonstream_success_closes_response(monkeypatch):
    response = _Response(payload={"choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)

    assert llm.chat([{"role": "user", "content": "hello"}]) == "ok"
    assert response.closed is True


def test_http_failure_closes_response(monkeypatch):
    response = _Response(status_code=503, text="gateway unavailable")
    monkeypatch.setattr(llm, "LLM_STREAMING", True)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: response)

    with pytest.raises(RuntimeError, match="HTTP 503"):
        llm.chat([{"role": "user", "content": "hello"}])

    assert response.closed is True
