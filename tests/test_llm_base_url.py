"""LLM gateway base URL validation."""

import pytest

import dm.llm as llm


@pytest.mark.parametrize("base_url", ["", " http://localhost:4000/v1", "http://localhost:4000/v1 ", "http://host\n/v1", 123])
def test_chat_rejects_invalid_gateway_base_url_before_request(monkeypatch, base_url):
    monkeypatch.setattr(llm, "LLM_BASE_URL", base_url)
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request should not be sent")),
    )

    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        llm.chat([{"role": "user", "content": "hello"}])
