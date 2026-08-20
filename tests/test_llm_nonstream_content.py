"""Non-stream LLM content type validation."""

import pytest

import dm.llm as llm


@pytest.mark.parametrize("content", [123, True, [], {}, ["text"]])
def test_chat_rejects_non_text_nonstream_content(monkeypatch, content):
    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: _Response())

    with pytest.raises(RuntimeError, match="content 不是文本"):
        llm.chat([{"role": "user", "content": "hello"}])


def test_chat_maps_null_nonstream_content_to_empty_string(monkeypatch):
    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": None}}]}

    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: _Response())

    assert llm.chat([{"role": "user", "content": "hello"}]) == ""
