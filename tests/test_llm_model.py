"""LLM model-name validation."""

import pytest

import dm.llm as llm


@pytest.mark.parametrize("model", ["", " qwen3:8b", "qwen3:8b ", "qwen\x00model", 123])
def test_chat_rejects_invalid_explicit_model_names(monkeypatch, model):
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="model"):
        llm.chat([{"role": "user", "content": "hello"}], model=model)


def test_chat_rejects_invalid_default_model_name(monkeypatch):
    monkeypatch.setattr(llm, "LLM_MODEL", "")
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="model"):
        llm.chat([{"role": "user", "content": "hello"}])


def test_chat_sends_explicit_model_name(monkeypatch):
    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    captured = {}
    monkeypatch.setattr(llm, "LLM_STREAMING", False)
    monkeypatch.setattr(llm.requests, "post", lambda *args, **kwargs: captured.update(kwargs) or _Response())

    assert llm.chat([{"role": "user", "content": "hello"}], model="qwen3:14b") == "ok"
    assert captured["json"]["model"] == "qwen3:14b"
