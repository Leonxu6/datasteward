"""LLM API key header validation."""

import pytest

import dm.llm as llm


@pytest.mark.parametrize(
    "api_key",
    [123, "token\nInjected: value", "token\rvalue", "token\x7f"],
)
def test_chat_rejects_unsafe_api_key_before_request(monkeypatch, api_key):
    monkeypatch.setattr(llm, "LLM_API_KEY", api_key)
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="LLM_API_KEY"):
        llm.chat([{"role": "user", "content": "hello"}])
