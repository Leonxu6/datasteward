"""LLM client sampling-temperature validation."""

import math

import pytest

import dm.llm as llm


@pytest.mark.parametrize("temperature", [True, False, "0.2", None, math.inf, -math.inf, math.nan])
def test_chat_rejects_non_numeric_or_non_finite_temperatures(monkeypatch, temperature):
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="temperature"):
        llm.chat([{"role": "user", "content": "hello"}], temperature=temperature)


def test_chat_preserves_finite_temperature(monkeypatch):
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

    assert llm.chat([{"role": "user", "content": "hello"}], temperature=0.0) == "ok"
    assert captured["json"]["temperature"] == 0.0
