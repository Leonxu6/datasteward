from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dm.channels import dingtalk


class _Response:
    def __init__(self, chunks, *, status_code=200, http_error=None):
        self.chunks = chunks
        self.status_code = status_code
        self.http_error = http_error
        self.closed = False

    def iter_content(self, *, chunk_size):
        assert chunk_size == dingtalk._WEBHOOK_RESPONSE_CHUNK_BYTES
        yield from self.chunks

    def raise_for_status(self):
        if self.http_error is not None:
            raise self.http_error

    def close(self):
        self.closed = True


def test_push_webhook_merges_signature_query_without_assuming_existing_query(monkeypatch):
    response = _Response([b'{"errcode":0,"errmsg":"ok"}'])
    post = Mock(return_value=response)
    monkeypatch.setattr(dingtalk.requests, "post", post)
    monkeypatch.setattr(dingtalk.time, "time", lambda: 1.234)

    dingtalk.push_webhook("hello", webhook="https://example.com/hook", secret="secret")

    url = post.call_args.args[0]
    assert url.startswith("https://example.com/hook?")
    assert "timestamp=1234" in url
    assert "sign=" in url
    assert post.call_args.kwargs["stream"] is True
    assert response.closed is True


def test_push_webhook_rejects_oversized_response_and_closes_it(monkeypatch):
    response = _Response([b"x" * 9, b"y" * 8])
    monkeypatch.setattr(dingtalk, "_WEBHOOK_RESPONSE_MAX_BYTES", 16)
    monkeypatch.setattr(dingtalk.requests, "post", Mock(return_value=response))

    with pytest.raises(RuntimeError, match="响应超过大小上限"):
        dingtalk.push_webhook("hello", webhook="https://example.com/hook")

    assert response.closed is True


def test_push_webhook_closes_http_error_response(monkeypatch):
    error = dingtalk.requests.HTTPError("service unavailable")
    response = _Response([], status_code=503, http_error=error)
    monkeypatch.setattr(dingtalk.requests, "post", Mock(return_value=response))

    with pytest.raises(dingtalk.requests.HTTPError):
        dingtalk.push_webhook("hello", webhook="https://example.com/hook")

    assert response.closed is True


def test_push_webhook_rejects_business_error_without_printing_backend_message(monkeypatch, capsys):
    response = _Response([b'{"errcode":310000,"errmsg":"private backend detail"}'])
    monkeypatch.setattr(dingtalk.requests, "post", Mock(return_value=response))

    with pytest.raises(RuntimeError, match="错误码 310000"):
        dingtalk.push_webhook("hello", webhook="https://example.com/hook")

    assert "private backend detail" not in capsys.readouterr().out
    assert response.closed is True


def test_push_webhook_rejects_duplicate_result_keys(monkeypatch):
    response = _Response([b'{"errcode":0,"errcode":310000}'])
    monkeypatch.setattr(dingtalk.requests, "post", Mock(return_value=response))

    with pytest.raises(RuntimeError, match="不是有效 JSON"):
        dingtalk.push_webhook("hello", webhook="https://example.com/hook")

    assert response.closed is True


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
