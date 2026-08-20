"""LLM client wall-clock timeout validation."""

import math

import pytest

import dm.llm as llm


@pytest.mark.parametrize("timeout", [0, -1, True, False, "30", None, math.inf, -math.inf, math.nan])
def test_chat_rejects_invalid_wall_clock_timeouts_before_request(monkeypatch, timeout):
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="timeout"):
        llm.chat([{"role": "user", "content": "hello"}], timeout=timeout)


def test_chat_accepts_fractional_positive_timeout(monkeypatch):
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

    assert llm.chat([{"role": "user", "content": "hello"}], timeout=2.5) == "ok"
    assert captured["timeout"] == 2.5
