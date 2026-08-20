"""Non-stream LLM response JSON handling."""

import pytest

import dm.llm as llm


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
