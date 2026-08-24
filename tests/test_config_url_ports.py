import pytest

from dm.config_validation import env_http_url


def test_service_urls_accept_explicit_nonzero_ports(monkeypatch):
    monkeypatch.setenv("DM_URL", "https://example.com:8443/api")
    assert env_http_url("DM_URL", "http://localhost") == "https://example.com:8443/api"


@pytest.mark.parametrize("value", ["https://example.com:", "https://example.com:0/api"])
def test_service_urls_reject_dangling_or_zero_ports(monkeypatch, value):
    monkeypatch.setenv("DM_URL", value)
    with pytest.raises(ValueError):
        env_http_url("DM_URL", "http://localhost")
