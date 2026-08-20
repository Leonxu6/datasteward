"""LLM message role validation."""

import pytest

import dm.llm as llm


@pytest.mark.parametrize("role", [" user", "user ", "\tuser", "user\n", "user\x00role"])
def test_chat_rejects_padded_or_control_character_roles(monkeypatch, role):
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="role"):
        llm.chat([{"role": role, "content": "hello"}])
