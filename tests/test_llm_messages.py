"""LLM chat message envelope validation."""

import pytest

import dm.llm as llm


@pytest.mark.parametrize(
    "messages",
    [None, {}, "hello", [], ["hello"], [{}], [{"role": "", "content": "x"}], [{"role": "user"}]],
)
def test_chat_rejects_invalid_message_envelopes_before_request(monkeypatch, messages):
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="messages"):
        llm.chat(messages)


def test_chat_preserves_valid_message_payload(monkeypatch):
    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    messages = [
        {"role": "system", "content": "be concise"},
        {"role": "user", "content": "hello"},
    ]
    captured = {}
    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: captured.update(kwargs) or _Response(),
    )

    assert llm.chat(messages) == "ok"
    assert captured["json"]["messages"] == messages
