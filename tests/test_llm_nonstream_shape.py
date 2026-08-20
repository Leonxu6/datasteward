"""Non-stream LLM response shape validation."""

import pytest

import dm.llm as llm


@pytest.mark.parametrize(
    "payload",
    [None, [], {}, {"choices": None}, {"choices": []}, {"choices": [None]}, {"choices": [{}]}, {"choices": [{"message": None}]}],
)
def test_chat_normalizes_malformed_nonstream_shapes(monkeypatch, payload):
    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return payload

    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: _Response())

    with pytest.raises(RuntimeError, match="响应结构异常"):
        llm.chat([{"role": "user", "content": "hello"}])
