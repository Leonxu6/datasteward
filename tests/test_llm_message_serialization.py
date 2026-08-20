"""LLM chat message JSON serialization validation."""

import pytest

import dm.llm as llm


@pytest.mark.parametrize(
    "content",
    [{1, 2}, object(), complex(1, 2)],
)
def test_chat_rejects_non_serializable_message_content(monkeypatch, content):
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="JSON"):
        llm.chat([{"role": "user", "content": content}])
