import pytest

from dm.llm import _gateway_base_url, _required_text


def test_required_text_errors_do_not_echo_rejected_values():
    secret = "token-secret\n"
    with pytest.raises(ValueError) as exc:
        _required_text(secret, field_name="model")
    assert "token-secret" not in str(exc.value)


def test_gateway_parse_errors_do_not_echo_rejected_urls():
    secret = "https://example.com:bad-secret-port"
    with pytest.raises(ValueError) as exc:
        _gateway_base_url(secret)
    assert "bad-secret-port" not in str(exc.value)
