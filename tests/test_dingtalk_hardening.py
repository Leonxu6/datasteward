from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dm.channels import dingtalk


def test_push_webhook_merges_signature_query_without_assuming_existing_query(monkeypatch):
    response = Mock(status_code=200, text="ok")
    response.raise_for_status.return_value = None
    post = Mock(return_value=response)
    monkeypatch.setattr(dingtalk.requests, "post", post)
    monkeypatch.setattr(dingtalk.time, "time", lambda: 1.234)

    dingtalk.push_webhook("hello", webhook="https://example.com/hook", secret="secret")

    url = post.call_args.args[0]
    assert url.startswith("https://example.com/hook?")
    assert "timestamp=1234" in url
    assert "sign=" in url
    response.raise_for_status.assert_called_once_with()


def test_push_webhook_rejects_insecure_url_before_network(monkeypatch):
    post = Mock()
    monkeypatch.setattr(dingtalk.requests, "post", post)
    with pytest.raises(ValueError):
        dingtalk.push_webhook("hello", webhook="http://example.com/hook")
    post.assert_not_called()


def test_push_webhook_rejects_blank_message_before_network(monkeypatch):
    post = Mock()
    monkeypatch.setattr(dingtalk.requests, "post", post)
    with pytest.raises(ValueError):
        dingtalk.push_webhook("   ", webhook="https://example.com/hook")
    post.assert_not_called()


def test_should_trigger_handles_non_string_message_content():
    incoming = SimpleNamespace(
        text=SimpleNamespace(content=None),
        conversation_type="1",
        is_in_at_list=False,
        chatbot_user_id="",
        at_users=[],
    )
    assert dingtalk.should_trigger(incoming) == (False, "")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"limit": True},
        {"limit": 65},
        {"queue_max": -1},
        {"queue_max": 1001},
        {"queue_timeout": 0},
        {"queue_timeout": float("inf")},
    ],
)
def test_gate_rejects_invalid_capacity_and_timeout_settings(kwargs):
    with pytest.raises(ValueError):
        dingtalk._Gate(**kwargs)


def test_gate_accepts_zero_waiting_capacity():
    gate = dingtalk._Gate(limit=2, queue_max=0, queue_timeout=30)
    assert gate.limit == 2
    assert gate.queue_max == 0
    assert gate.queue_timeout == 30
