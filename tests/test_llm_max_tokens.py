"""LLM client max-token validation."""

import pytest

import dm.llm as llm


@pytest.mark.parametrize("max_tokens", [0, -1, True, False, 1.5, "100"])
def test_chat_rejects_invalid_max_tokens_before_request(monkeypatch, max_tokens):
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="max_tokens"):
        llm.chat([{"role": "user", "content": "hello"}], max_tokens=max_tokens)


def test_chat_sends_positive_max_tokens(monkeypatch):
    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    captured = {}
    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: captured.update(kwargs) or _Response(),
    )

    assert llm.chat([{"role": "user", "content": "hello"}], max_tokens=512) == "ok"
    assert captured["json"]["max_tokens"] == 512
